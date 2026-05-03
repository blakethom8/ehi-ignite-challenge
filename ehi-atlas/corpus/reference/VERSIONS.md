# Reference Terminology Versions

> Pinned versions of all reference terminologies used by Layer 3 code mapping. When upgrading, document the bump here and verify Layer 3 tests still pass.

## Currently pinned

| Terminology | Version | Source | Status |
|---|---|---|---|
| UMLS Metathesaurus | _deferred to Phase 2_ | nlm.nih.gov | **Phase 1:** hand-curated crosswalk for showcase codes only — `corpus/reference/handcrafted-crosswalk/showcase.json`. Decision D9 in BUILD-TRACKER: full UMLS load (3M+ concepts) = Phase 2 pending Blake's UMLS license registration. |
| RxNorm | _no local snapshot_ | rxnav.nlm.nih.gov REST API | **Phase 1:** REST API client at `ehi_atlas/terminology/rxnorm.py` with file-based cache at `corpus/reference/rxnorm/.cache/`. No auth required. Key RxCUIs: simvastatin=36567, atorvastatin=83367, fluticasone/salmeterol=896188. |
| LOINC | _static showcase subset_ | loinc.org (public search) | **Phase 1:** static 22-code subset at `corpus/reference/loinc/showcase-loinc.json` (showcase patient panels + document type code). Full LOINC download (requires free account at loinc.org) = Phase 2. Codes verified against LOINC 2.77. |
| HL7 ConceptMaps | _not currently used_ | terminology.hl7.org | Not currently used. Available for adoption in Phase 2 if needed for FHIR R4 concept map lookups. |
| SNOMED CT US Edition | _partial via crosswalk_ | umls.nlm.nih.gov | **Phase 1:** showcase codes covered via hand-curated crosswalk (`corpus/reference/handcrafted-crosswalk/showcase.json`). Full US Edition (under UMLS license) = Phase 2. |
| ICD-10-CM | _partial via crosswalk_ | cms.gov | **Phase 1:** showcase codes covered via hand-curated crosswalk. Full ICD-10-CM code set (public domain, CMS download) = Phase 2. |

## Upgrade procedure

When a new release of a terminology is needed:

1. Verify backward compatibility of code mappings (run Layer 3 tests against new snapshot)
2. Update this file with the new version number and date
3. Bump `harmonizer_version` in `manifest.json` if any merge behavior changed
4. Add an entry to `docs/mapping-decisions.md` explaining the upgrade

## Storage

Terminology snapshots themselves are large (~10 GB for UMLS) and live in `corpus/reference/{name}/` — gitignored. The pinning information is what's tracked.

Phase 1 artifacts that ARE tracked in git:

| File | Description |
|---|---|
| `corpus/reference/loinc/showcase-loinc.json` | 22-code LOINC static subset |
| `corpus/reference/handcrafted-crosswalk/showcase.json` | 17-entry SNOMED/ICD-10/RxNorm crosswalk |
| `ehi_atlas/terminology/rxnorm.py` | RxNorm REST client + file-based cache |
| `ehi_atlas/terminology/__init__.py` | Loader module + `lookup_cross()` helper |

The RxNorm `.cache/` directory is gitignored (auto-populated on first run).

## Phase 1 / Phase 2 split

Phase 1 (current) covers only the showcase patient codes needed to demonstrate all 5 harmonization artifacts. Phase 2 expands to full UMLS / LOINC / SNOMED coverage once:

1. Blake completes UMLS license registration (task 1.4 in BUILD-TRACKER)
2. The LOINC free-account download is completed (loinc.org)
3. The full SNOMED CT US Edition is available via UMLS

Until then, any Layer 3 code outside the showcase set will fall through to `lookup_cross() -> None` and require human review.
