# Cedars-Sinai MyHealth — PDF Parsing Review

## Premise
First comparison source. User reports our PDF parser produces different results than Function Health's parser when given a Cedars-Sinai MyHealth portal export. Goal: figure out what's different and why.

## Files in this folder

### inputs/
Drop here:
- The MyHealth PDF
- Any sibling JSON (e.g., a SMART-pulled FHIR Bundle for ground truth)
- HAR log of the Function Health upload flow (so we can see what they sent and got back)

### function-health-output/
What Function Health's parser returned for this PDF.

### our-output/
What our `multipass-fhir` pipeline produces. Files written here by `pdf-review/scripts/`.

## Working notes

*(Append as we go. Each entry dated.)*

### 2026-05-07 — Folder set up, awaiting inputs
- [ ] User to drop PDF + JSON + HAR in `inputs/`
- [ ] User to share what Function Health's output looked like and where the discrepancy is
- [ ] Then: run `multipass-fhir` against the PDF, diff our output vs theirs

## Questions to answer once content arrives

1. **Output shape from Function Health.** FHIR Bundle? Custom JSON? Per-resource list? What schema?
2. **Are discrepancies in extraction, normalization, or both?**
   - Extraction: a fact present in their output is missing from ours (or vice versa)
   - Normalization: same fact, different code (e.g., they use SNOMED, we use ICD-10) or different display text
3. **Resource type breakdown.** Where do the diffs concentrate — labs, conditions, medications, allergies, immunizations, procedures?
4. **Source PDF characteristics.** Text-layer or scanned? Page count? Section structure (problem list, lab tab, etc.)?
5. **Function Health's apparent strategy.** From the HAR log — is it OCR-then-NER, vision, hybrid? Single-call or multi-pass? Cloud API (AWS Comprehend / Google Healthcare NLP) underneath?
