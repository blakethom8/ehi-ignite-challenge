# EHI Ignite Report Build Checklist

## Submission requirements to verify in portal

- [ ] Final deadline shown in portal.
- [ ] Page limit.
- [ ] Font requirement.
- [ ] Required fields outside PDF.
- [ ] Whether screenshots/mockups count inside page limit.
- [ ] File size limit.
- [ ] Whether team lead bio has separate field or belongs in PDF.
- [ ] Whether commitment to Phase 2 is explicit checkbox/text.

## Narrative decisions

- [ ] Final product name.
- [ ] Primary scenario ordering: Integration Across Settings vs Interactive Patient Tools vs Clinical Domain Customization.
- [ ] Primary demo story: second opinion, pre-op review, caregiver handoff, or general patient record workspace.
- [ ] How much to emphasize local MedGemma/Ollama testing.
- [ ] How much to emphasize current prototype vs planned Phase 2 build.

## Evidence to collect

- [ ] Current app screenshots.
- [ ] Architecture diagram export as PNG/SVG.
- [ ] PDF extraction benchmark table.
- [ ] MedGemma smoke test artifact summary.
- [ ] FHIR corpus stats.
- [ ] Privacy/security deployment assumptions.

## Report sections

- [ ] 1-page executive narrative.
- [ ] Problem and user need.
- [ ] Solution architecture.
- [ ] Use cases / scenarios addressed.
- [ ] Product workflow and wireframes.
- [ ] Technical feasibility.
- [ ] Innovation / AI transparency.
- [ ] Privacy and security.
- [ ] Potential impact.
- [ ] Team / entity description.

## Language rules

Use:

- “FHIR-compatible clinical fact graph”
- “structured clinical substrate for trustworthy AI”
- “language model reasoning layer over an auditable record”
- “parse once, structure once, validate once, cite forever”
- “source-backed summaries, charts, contradiction checks, and handoffs”

Avoid overclaiming:

- Do not imply FHIR gives automatic access to every EHR.
- Do not imply the prototype is fully production/HIPAA certified.
- Do not imply local MedGemma is already the winning extraction model.
- Do not say CDA/C-CDA are obsolete; say they are important inputs but not ideal reasoning substrates.
- Do not frame as “FHIR is a universal language model layer” without explaining that FHIR is the evidence substrate, not the model layer itself.


## New highest-value demo artifact

- [ ] Portable workspace zip package for one safe/demo patient.
- [ ] C-CDA included as an input source or staged sample.
- [ ] CLI/package review commands.
- [ ] Claude raw files vs Atlas package comparison.
- [ ] Codex raw files vs Atlas package comparison.
- [ ] Compact evaluation table added to final PDF.
