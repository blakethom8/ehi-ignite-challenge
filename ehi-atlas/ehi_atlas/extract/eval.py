"""Ground-truth eval harness for vision-extraction outputs.

Compares an :class:`ExtractionResult` (what our PDF → FHIR pipeline produced)
against a :class:`ClientFullEHR` JSON (Josh Mandel's shape — the structured
truth from a SMART pull). The diff surfaces three classes of finding:

1. **Schema gaps** — fact types present in the ground truth that our
   ``ExtractedClinicalNote`` schema has no slot for (medications,
   allergies, immunizations, etc.). The eval reports these by listing
   any fact type where the ground-truth count is non-zero but our
   extracted count is zero.

2. **In-schema misses** — facts the model could have extracted but didn't.
   Conditions are the obvious one; if the FHIR has 28 conditions and
   our PDF extraction got 5, we have a recall problem within the
   schema we already support.

3. **Vision wins (extras)** — facts the model extracted that aren't in
   the ground truth. Some are model errors. Some are *real* — the FHIR
   doesn't always code every clinical finding (free-text in notes
   often beats structured Condition resources). The eval flags them
   so a human can sort.

Matching strategy
-----------------
Per fact type, try in order:

  1. **Exact code match** on the canonical terminology
     (ICD-10-CM / SNOMED for conditions, RxNorm for medications,
     CVX for vaccines, LOINC for labs).
  2. **Fuzzy display match** by token overlap (Jaccard-like).
     Defaults to threshold=0.5 — adjust if too strict / loose.
  3. **No match** → counts as missed (in ground truth) or extra
     (in extraction).

The matcher does NOT do clinical synonymy or semantic similarity —
"hyperlipidemia" and "high cholesterol" wouldn't match unless they
share an ICD-10 code or a token like "lipid". That's a real limit;
upgrade to embeddings if it becomes the bottleneck.

Output
------
:func:`evaluate` returns an :class:`EvalReport`. Use
:func:`format_markdown` to produce a copy-pasteable summary table
with per-type precision/recall/F1, schema-gap callouts, and lists
of missed / extra facts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from ehi_atlas.extract.schemas import ExtractionResult


FactType = Literal["condition", "medication", "allergy", "immunization", "lab"]


# ---------------------------------------------------------------------------
# Fact normalization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fact:
    """A canonical, comparable record for one clinical fact."""

    fact_type: FactType
    primary_code_system: str | None  # "icd-10-cm", "snomed", "rxnorm", "loinc", "cvx"
    primary_code: str | None
    display: str  # human-readable, lowercased / stripped
    source_path: str  # debug breadcrumb pointing back to the original record

    # All terminologies present (handy for downstream code-matching)
    all_codes: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ground truth: ClientFullEHR JSON → list[Fact]
# ---------------------------------------------------------------------------


_CODE_SYSTEM_LOOKUP = {
    "http://hl7.org/fhir/sid/icd-10-cm": "icd-10-cm",
    "http://hl7.org/fhir/sid/icd-10": "icd-10-cm",
    "http://snomed.info/sct": "snomed",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "rxnorm",
    "http://loinc.org": "loinc",
    "http://hl7.org/fhir/sid/cvx": "cvx",
    "http://hl7.org/fhir/sid/ndc": "ndc",
}


def _short_system(system: str) -> str:
    """Normalize an FHIR coding.system URI to a short tag (icd-10-cm, snomed, ...)."""
    if not system:
        return ""
    if system in _CODE_SYSTEM_LOOKUP:
        return _CODE_SYSTEM_LOOKUP[system]
    # Heuristic — last URL path segment lowercased
    return system.rsplit("/", 1)[-1].lower()


def _pick_code(
    coding: list[dict] | None,
    preferred: list[str],
) -> tuple[str | None, str | None, dict[str, str]]:
    """From a FHIR coding[] array, pick the first ``preferred`` system match.

    Returns ``(system_short, code, all_codes)`` where ``all_codes`` is a
    ``{system_short: code}`` dict of every coding available.
    """
    all_codes: dict[str, str] = {}
    if not coding:
        return None, None, all_codes
    for c in coding:
        sys_short = _short_system(c.get("system", ""))
        code = c.get("code")
        if sys_short and code is not None:
            all_codes.setdefault(sys_short, str(code))
    for pref in preferred:
        if pref in all_codes:
            return pref, all_codes[pref], all_codes
    if all_codes:
        first = next(iter(all_codes.items()))
        return first[0], first[1], all_codes
    return None, None, all_codes


def _normalize_display(s: str | None) -> str:
    return (s or "").strip().lower()


def facts_from_clientfullehr(payload: dict | list) -> list[Fact]:
    """Walk a ClientFullEHR JSON and emit a Fact per clinically-meaningful resource.

    Accepts either the raw JSON (a list with one wrapper dict containing ``fhir``)
    or just the wrapper dict itself.
    """
    # Some Health Skillz exports wrap the bundle in a single-element list
    if isinstance(payload, list):
        if not payload:
            return []
        payload = payload[0]
    fhir = payload.get("fhir", {}) if isinstance(payload, dict) else {}

    facts: list[Fact] = []

    # --- Conditions ---
    for c in fhir.get("Condition", []):
        code = c.get("code") or {}
        sys_short, code_value, all_codes = _pick_code(
            code.get("coding"), preferred=["icd-10-cm", "snomed"]
        )
        display = code.get("text") or _best_display_from_coding(code.get("coding"))
        facts.append(
            Fact(
                fact_type="condition",
                primary_code_system=sys_short,
                primary_code=code_value,
                display=_normalize_display(display),
                source_path=f"Condition/{c.get('id', '')}",
                all_codes=all_codes,
            )
        )

    # --- Medications (via MedicationRequest.medicationReference.display + Medication.code) ---
    medications_by_id = {m.get("id"): m for m in fhir.get("Medication", [])}
    for mr in fhir.get("MedicationRequest", []):
        med_ref = mr.get("medicationReference") or {}
        med_display = med_ref.get("display", "")
        med_codes: dict[str, str] = {}
        sys_short = code_value = None
        # Try to resolve the Medication resource by id (strip the "Medication/" prefix)
        ref_str = med_ref.get("reference", "")
        med_id = ref_str.split("/", 1)[1] if "/" in ref_str else ""
        med = medications_by_id.get(med_id)
        if med:
            mc = med.get("code") or {}
            sys_short, code_value, med_codes = _pick_code(
                mc.get("coding"), preferred=["rxnorm", "ndc"]
            )
            if not med_display:
                med_display = mc.get("text", "")
        # MedicationCodeableConcept inline path
        mcc = mr.get("medicationCodeableConcept") or {}
        if mcc:
            mc_text = mcc.get("text", "")
            if not med_display:
                med_display = mc_text
            sys2, code2, codes2 = _pick_code(
                mcc.get("coding"), preferred=["rxnorm", "ndc"]
            )
            med_codes.update(codes2)
            if not code_value:
                sys_short, code_value = sys2, code2
        facts.append(
            Fact(
                fact_type="medication",
                primary_code_system=sys_short,
                primary_code=code_value,
                display=_normalize_display(med_display),
                source_path=f"MedicationRequest/{mr.get('id', '')}",
                all_codes=med_codes,
            )
        )

    # --- Allergies ---
    for a in fhir.get("AllergyIntolerance", []):
        code = a.get("code") or {}
        sys_short, code_value, all_codes = _pick_code(
            code.get("coding"), preferred=["snomed", "rxnorm"]
        )
        display = code.get("text") or _best_display_from_coding(code.get("coding"))
        facts.append(
            Fact(
                fact_type="allergy",
                primary_code_system=sys_short,
                primary_code=code_value,
                display=_normalize_display(display),
                source_path=f"AllergyIntolerance/{a.get('id', '')}",
                all_codes=all_codes,
            )
        )

    # --- Immunizations ---
    for imm in fhir.get("Immunization", []):
        vc = imm.get("vaccineCode") or {}
        sys_short, code_value, all_codes = _pick_code(
            vc.get("coding"), preferred=["cvx", "ndc"]
        )
        display = vc.get("text") or _best_display_from_coding(vc.get("coding"))
        facts.append(
            Fact(
                fact_type="immunization",
                primary_code_system=sys_short,
                primary_code=code_value,
                display=_normalize_display(display),
                source_path=f"Immunization/{imm.get('id', '')}",
                all_codes=all_codes,
            )
        )

    # --- Lab Observations only (skip social-history, vitals for now) ---
    for obs in fhir.get("Observation", []):
        if not _is_laboratory(obs):
            continue
        code = obs.get("code") or {}
        sys_short, code_value, all_codes = _pick_code(
            code.get("coding"), preferred=["loinc", "snomed"]
        )
        display = code.get("text") or _best_display_from_coding(code.get("coding"))
        facts.append(
            Fact(
                fact_type="lab",
                primary_code_system=sys_short,
                primary_code=code_value,
                display=_normalize_display(display),
                source_path=f"Observation/{obs.get('id', '')}",
                all_codes=all_codes,
            )
        )

    return facts


def _best_display_from_coding(coding: list[dict] | None) -> str:
    """When ``code.text`` is missing, fall back to the first coding's display."""
    if not coding:
        return ""
    for c in coding:
        if c.get("display"):
            return c["display"]
    return ""


def _is_laboratory(observation: dict) -> bool:
    """True if the Observation has category=laboratory."""
    cats = observation.get("category", [])
    if not isinstance(cats, list):
        return False
    for cat in cats:
        for coding in (cat or {}).get("coding", []):
            if coding.get("code") == "laboratory":
                return True
    return False


# ---------------------------------------------------------------------------
# Extraction: ExtractionResult → list[Fact]
# ---------------------------------------------------------------------------


def facts_from_extraction(result: ExtractionResult) -> list[Fact]:
    doc = result.document
    facts: list[Fact] = []

    if doc.document_type == "lab-report":
        for r in doc.results:
            sys_short = "loinc" if r.loinc_code else None
            facts.append(
                Fact(
                    fact_type="lab",
                    primary_code_system=sys_short,
                    primary_code=r.loinc_code,
                    display=_normalize_display(r.test_name),
                    source_path=f"ExtractedLabResult/{r.test_name}",
                    all_codes={"loinc": r.loinc_code} if r.loinc_code else {},
                )
            )
    else:  # clinical-note
        for c in doc.extracted_conditions:
            primary_sys = (
                "icd-10-cm" if c.icd_10_cm_code
                else "snomed" if c.snomed_ct_code
                else None
            )
            primary_code = c.icd_10_cm_code or c.snomed_ct_code
            all_codes: dict[str, str] = {}
            if c.icd_10_cm_code:
                all_codes["icd-10-cm"] = c.icd_10_cm_code
            if c.snomed_ct_code:
                all_codes["snomed"] = c.snomed_ct_code
            facts.append(
                Fact(
                    fact_type="condition",
                    primary_code_system=primary_sys,
                    primary_code=primary_code,
                    display=_normalize_display(c.label),
                    source_path=f"ExtractedCondition/{c.label[:30]}",
                    all_codes=all_codes,
                )
            )
        # Symptoms aren't a separate FHIR resource type in our ground truth,
        # so they don't participate in the eval here. They could be mapped
        # to Observation(category=symptom) in a future pass.

    return facts


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    return set(_TOKEN_RE.findall(s.lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class FactMatch:
    extracted: Fact
    ground_truth: Fact
    score: float
    method: Literal["code", "fuzzy"]


def match_facts(
    extracted: list[Fact],
    ground_truth: list[Fact],
    *,
    threshold: float = 0.5,
) -> tuple[list[FactMatch], list[Fact], list[Fact]]:
    """Bipartite-greedy match extracted to ground_truth.

    Returns ``(matches, extras, missed)``:
      - matches: pairs that were linked, with score + method
      - extras: extracted facts with no match (false positives)
      - missed: ground-truth facts with no match (false negatives)
    """
    matches: list[FactMatch] = []
    used_gt: set[int] = set()

    # Pass 1: exact code match (cross-system OK if both fact types match)
    for ef in extracted:
        if not ef.primary_code:
            continue
        for i, gf in enumerate(ground_truth):
            if i in used_gt:
                continue
            if ef.fact_type != gf.fact_type:
                continue
            # Match if any code in either record matches in any system
            ext_codes = ef.all_codes or {ef.primary_code_system or "_": ef.primary_code}
            gt_codes = gf.all_codes or {gf.primary_code_system or "_": gf.primary_code}
            shared = set(ext_codes.items()) & set(gt_codes.items())
            if shared:
                matches.append(FactMatch(ef, gf, score=1.0, method="code"))
                used_gt.add(i)
                break

    # Pass 2: fuzzy display match for unmatched extracted
    matched_extracted_ids = {id(m.extracted) for m in matches}
    for ef in extracted:
        if id(ef) in matched_extracted_ids:
            continue
        best_idx = -1
        best_score = 0.0
        for i, gf in enumerate(ground_truth):
            if i in used_gt:
                continue
            if ef.fact_type != gf.fact_type:
                continue
            score = _jaccard(ef.display, gf.display)
            if score >= threshold and score > best_score:
                best_idx = i
                best_score = score
        if best_idx >= 0:
            matches.append(
                FactMatch(ef, ground_truth[best_idx], score=best_score, method="fuzzy")
            )
            used_gt.add(best_idx)

    matched_extracted_ids = {id(m.extracted) for m in matches}
    extras = [ef for ef in extracted if id(ef) not in matched_extracted_ids]
    missed = [gf for i, gf in enumerate(ground_truth) if i not in used_gt]
    return matches, extras, missed


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@dataclass
class TypeReport:
    fact_type: FactType
    gt_count: int
    extracted_count: int
    matches: list[FactMatch]
    extras: list[Fact]
    missed: list[Fact]

    @property
    def tp(self) -> int:
        return len(self.matches)

    @property
    def fp(self) -> int:
        return len(self.extras)

    @property
    def fn(self) -> int:
        return len(self.missed)

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def is_schema_gap(self) -> bool:
        """True if ground truth has facts of this type but our schema produced none."""
        return self.gt_count > 0 and self.extracted_count == 0


@dataclass
class EvalReport:
    by_type: dict[FactType, TypeReport]
    extraction_label: str = ""
    ground_truth_label: str = ""

    @property
    def schema_gaps(self) -> list[FactType]:
        return [ft for ft, r in self.by_type.items() if r.is_schema_gap]


_FACT_TYPES: list[FactType] = ["condition", "medication", "allergy", "immunization", "lab"]


def evaluate(
    ground_truth: dict | list,
    extraction: ExtractionResult,
    *,
    extraction_label: str = "",
    ground_truth_label: str = "",
    fuzzy_threshold: float = 0.5,
) -> EvalReport:
    gt_facts = facts_from_clientfullehr(ground_truth)
    ex_facts = facts_from_extraction(extraction)

    by_type: dict[FactType, TypeReport] = {}
    for ft in _FACT_TYPES:
        gt_t = [f for f in gt_facts if f.fact_type == ft]
        ex_t = [f for f in ex_facts if f.fact_type == ft]
        matches, extras, missed = match_facts(ex_t, gt_t, threshold=fuzzy_threshold)
        by_type[ft] = TypeReport(
            fact_type=ft,
            gt_count=len(gt_t),
            extracted_count=len(ex_t),
            matches=matches,
            extras=extras,
            missed=missed,
        )

    return EvalReport(
        by_type=by_type,
        extraction_label=extraction_label,
        ground_truth_label=ground_truth_label,
    )


def format_markdown(report: EvalReport, *, max_examples: int = 8) -> str:
    """Render an EvalReport as a copy-pasteable markdown table + lists."""
    lines: list[str] = []
    if report.extraction_label or report.ground_truth_label:
        lines.append(f"# Extraction eval — {report.extraction_label} vs {report.ground_truth_label}")
        lines.append("")

    # Per-type summary table
    lines.append("## Per-type summary")
    lines.append("")
    lines.append("| type | ground truth | extracted | TP | FP | FN | precision | recall | F1 | note |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for ft in _FACT_TYPES:
        r = report.by_type[ft]
        note = ""
        if r.is_schema_gap:
            note = "**SCHEMA GAP** (no slot in ExtractionResult)"
        elif r.gt_count == 0 and r.extracted_count == 0:
            note = "(neither side has any)"
        lines.append(
            f"| {ft} | {r.gt_count} | {r.extracted_count} | {r.tp} | {r.fp} | {r.fn} | "
            f"{r.precision:.2f} | {r.recall:.2f} | {r.f1:.2f} | {note} |"
        )
    lines.append("")

    # Schema gaps callout
    gaps = report.schema_gaps
    if gaps:
        lines.append("## Schema gaps")
        lines.append("")
        lines.append(
            "These fact types exist in the ground truth but our extraction "
            "schema has no slot to hold them:"
        )
        for ft in gaps:
            r = report.by_type[ft]
            lines.append(f"- **{ft}** — {r.gt_count} facts in ground truth, 0 extracted")
            for f in r.missed[:max_examples]:
                code = f"{f.primary_code_system}:{f.primary_code}" if f.primary_code else "no code"
                lines.append(f"    - `{code}` {f.display!r}")
            if len(r.missed) > max_examples:
                lines.append(f"    - … ({len(r.missed) - max_examples} more)")
        lines.append("")

    # Per-type missed + extra (for in-schema types only)
    lines.append("## Per-type detail")
    for ft in _FACT_TYPES:
        r = report.by_type[ft]
        if r.is_schema_gap or (r.gt_count == 0 and r.extracted_count == 0):
            continue
        lines.append("")
        lines.append(f"### {ft} (P={r.precision:.2f} · R={r.recall:.2f} · F1={r.f1:.2f})")
        if r.matches:
            lines.append(f"**Matched ({len(r.matches)}):**")
            for m in r.matches[:max_examples]:
                method = m.method
                lines.append(
                    f"  - [{method} {m.score:.2f}] {m.extracted.display!r} ↔ {m.ground_truth.display!r}"
                )
            if len(r.matches) > max_examples:
                lines.append(f"  - … ({len(r.matches) - max_examples} more)")
        if r.missed:
            lines.append(f"**Missed ({len(r.missed)}):**")
            for f in r.missed[:max_examples]:
                code = f"{f.primary_code_system}:{f.primary_code}" if f.primary_code else "—"
                lines.append(f"  - `{code}` {f.display!r}")
            if len(r.missed) > max_examples:
                lines.append(f"  - … ({len(r.missed) - max_examples} more)")
        if r.extras:
            lines.append(f"**Extra (extracted, not in ground truth — review for vision wins vs hallucinations) ({len(r.extras)}):**")
            for f in r.extras[:max_examples]:
                code = f"{f.primary_code_system}:{f.primary_code}" if f.primary_code else "—"
                lines.append(f"  - `{code}` {f.display!r}")
            if len(r.extras) > max_examples:
                lines.append(f"  - … ({len(r.extras) - max_examples} more)")

    return "\n".join(lines) + "\n"
