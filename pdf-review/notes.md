# PDF Parsing Review — Notes

Append-only working notes. Each section is dated. Add observations, surprises, and decisions as we work through the comparison.

---

## Session 1 — 2026-05-07

### Premise
User reports different results from our PDF parser vs Function Health's parser for the same source PDF. Setting up this scratch folder so we can:
- Drop PDFs into `inputs/`
- Drop Function Health's parser output into `function-health-output/`
- Run our parser, capture output in `our-output/`
- Diff and document findings here

### Awaiting from user
- [ ] One or more PDFs to put in `inputs/`
- [ ] Function Health parser output (JSON? PDF report? CSV?) for the same PDFs
- [ ] Specific symptoms / discrepancies the user observed (which fields, which values)

### Initial questions to answer once content is here
1. **What output shape does Function Health produce?** (FHIR Bundle? Custom JSON? CSV with their own schema?) — drives how we diff.
2. **Are the discrepancies in extraction (we missed something they got) or normalization (different code, different units, different display name for the same thing)?**
3. **Are they on tabular content (labs, vitals) or narrative (notes, conditions)?** — directs which pipeline pass to inspect.
4. **Is the source PDF text-layer or scanned image?** — drives whether OCR fallback would help.

---

*(Add new sessions below.)*

---

## Session 2 — 2026-05-07 — blake-functionhealth-2025-11-19

First real comparison. Source: Quest CMP/CBC/urinalysis lab from 11/19/2025 uploaded to Function Health. Captured FH parser output via HAR. Compared to our `multipass-fhir` output. Full per-source notes: `pdf-review/blake-functionhealth-2025-11-19/notes.md`.

### Cross-cutting findings (apply beyond this one PDF)

1. **Reading HAR files for parser comparison — gotcha.** Function Health uses a list+detail pattern. The polling endpoint `parsed/pending` only shows already-parsed docs; new uploads sit in `status: parsing` and don't appear there. The actual parsed output lives at `GET /parsed/{id}`. Fail-mode: capturing only polling responses gives you data about a different document. This is general — any "pending list" / "detail" split has this trap.

2. **Extraction quality is comparable; enrichment is the gap.** On a 57-test PDF with mixed panels (CMP, urinalysis, CBC, etc.), both parsers got 57 of 57. We even got one extra (BUN/Cr ratio FH missed). Where we lose is *post-extraction* — code resolution, interpretation flagging, clinical categorization.

3. **LOINC normalization is the #1 gap, and it's coupled to display-name normalization.** FH consistently expands abbreviations to "Full Name (ABBR)" form (e.g., `eGFR` → `Estimated Glomerular Filtration Rate (eGFR)`). That expansion is almost certainly what enables their LOINC matching. Two-step solution: normalize names first, then look up codes.

4. **FH does NOT capture ordering physician or patient identity.** We do. For cross-source harmonization (which patient does this lab belong to?), our metadata is more useful. This is a real differentiator we can lean on.

5. **The "wedge" framing holds at the extraction layer.** Vision-LLM extraction produces comparable test-level coverage to whatever FH is using underneath. The wedge story isn't "we extract more facts than them" — it's "we extract comparable facts, *and* with patient identity, *and* in interoperable FHIR Bundle shape, *and* with full provenance."

### New tasks surfaced for the deepening plan

These are appended to the working log's P1 list (`docs/daily/2026-05-07-ClaudeCode.md` Entry 2):

- **CODE-RESOLUTION-POST-PASS** — local LOINC lookup table + display-name normalization to enable code emission. Largest concrete deficit closer.
- **INTERPRETATION-POST-PASS** — compute `interpretation: H | L | N | A` from value vs reference range. No LLM needed.
- **CLINICAL-CATEGORY-EXTENSION** — add Metabolic/Kidney/Liver/etc. category to each Observation. Drive from LOINC after CODE-RESOLUTION lands.
- **DATE-PRECISION-FIX** — capture collection date AND report date AND received date separately. Per-Observation `effectiveDateTime` should be collection, not report.
- **PATIENT-SUMMARY-PASS** (optional/UX) — generate summary paragraph + 5 patient-friendly questions per bundle. Surfaces in Clinical Insights.

### Decisions parked
- Should code-resolution be a separate post-pass module, or rolled into the existing per-resource passes? (Lean: separate post-pass — keeps the LLM prompt focused on extraction; resolution is deterministic/lookup-table.)
- Local LOINC table vs external API? (Lean: local table first; API as fallback for unknowns.)
- Whether to wait for PDF-LAB-STUDIO before measuring whether code-resolution improves F1, or ship it now with a one-off bake-off comparison. (Open.)

