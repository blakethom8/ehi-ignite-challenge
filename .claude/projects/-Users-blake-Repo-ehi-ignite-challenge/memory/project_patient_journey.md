---
name: Patient Journey app scaffolding complete
description: The patient-journey/ Streamlit app has been scaffolded with 4 views, core modules, drug classifier, and episode detector. Ready for iteration.
type: project
---

As of 2026-03-29, the `patient-journey/` directory is fully scaffolded:
- **app.py** — Streamlit entry point with sidebar patient picker + file upload
- **core/loader.py** — wraps fhir_explorer parser
- **core/drug_classifier.py** — keyword + RxNorm mapping to 12 surgical-risk drug classes
- **core/episode_detector.py** — groups MedicationRequests into episodes, links conditions to encounters/meds
- **views/safety_panel.py** — Pre-op flags (critical/warning/info)
- **views/journey_timeline.py** — Plotly Gantt medication bars + encounter/procedure/diagnosis overlays
- **views/medication_history.py** — deep dive with drug class filtering, episode cards, prescription history
- **views/condition_tracker.py** — condition timeline (px.timeline), active/resolved filtering, linked meds/encounters
- **data/drug_classes.json** — 12 categories with keywords + RxNorm codes
- **tests/test_drug_classifier.py** — 7 passing tests

**Why:** Max (neurosurgeon) needs to answer "is this patient on blood thinners?" in 5 minutes before a case. The visualization layer is the core differentiator for the competition.

**How to apply:** This app is the primary competition deliverable. Next steps are running it via Streamlit, iterating on visualizations, and adding the NL search view.
