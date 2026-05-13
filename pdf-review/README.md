# PDF Parsing Review

Scratch workspace for hands-on PDF parser review. Distinct from the planned `PDF-LAB-STUDIO` (the full Streamlit test bench in `.claude/pdf-lab-studio-queue.md`) — this folder is the lower-friction equivalent: drop PDFs, drop comparative outputs from other parsers (e.g., Function Health), run small ad-hoc scripts, capture findings.

## Layout

Each source PDF gets its own folder (e.g., `cedars-myhealth/`). Inside each folder, the same three subdirs.

```
pdf-review/
├── README.md                       ← this file (committed)
├── notes.md                        ← cross-cutting findings / session log (committed)
├── scripts/                        ← reusable test scripts (committed)
└── <pdf-source-name>/              ← one folder per PDF source we're reviewing
    ├── notes.md                    ← per-source findings (committed)
    ├── inputs/                     ← PDF, JSON, HAR logs from the user (gitignored — PHI risk)
    ├── function-health-output/     ← Function Health (or other parser) output (gitignored)
    └── our-output/                 ← what our PDF parser produces (gitignored)
```

Currently active sources:
- `cedars-myhealth/` — Cedars-Sinai MyHealth portal export (first comparison)

## Conventions

### Naming inside a per-source folder
Use the same stem across the three subdirs so files line up:

```
cedars-myhealth/inputs/2025-11-29-myhealth.pdf
cedars-myhealth/inputs/2025-11-29-myhealth.json          ← e.g., a sibling structured export
cedars-myhealth/inputs/2025-11-29-myhealth.har           ← network capture from Function Health upload
cedars-myhealth/function-health-output/2025-11-29-myhealth.json
cedars-myhealth/our-output/2025-11-29-myhealth.bundle.json
cedars-myhealth/our-output/2025-11-29-myhealth.runs/{pass}/{prompt.txt,response.json}
```

### What gets committed
- ✅ `README.md`, `notes.md` (top + per-source), `scripts/*` — the work product
- ❌ `*/inputs/`, `*/function-health-output/`, `*/our-output/` — gitignored. Real PDFs, parser outputs, and HAR logs may contain PHI. Never commit.

### Adding a new source
1. `mkdir -p pdf-review/<source-name>/{inputs,function-health-output,our-output}` and `touch */{inputs,function-health-output,our-output}/.gitkeep`
2. Create `pdf-review/<source-name>/notes.md` with a short premise.
3. Drop files into `inputs/` and `function-health-output/`.
4. Run scripts (or ask Claude) to populate `our-output/`.
5. Capture diffs and surprises in the per-source `notes.md`. Cross-cutting patterns go in the top-level `notes.md`.

### HAR logs
HTTP archive captures are useful for reverse-engineering what other parsers do (e.g., capturing the Function Health upload→response flow). They're often large (multi-MB) and may contain auth cookies / PHI — they live in `inputs/` and stay gitignored.

## Why this exists

The user reported seeing different results from our PDF parser vs Function Health for the same PDF. That's a measurable difference worth investigating empirically — not an architecture conversation. This folder is for the empirical work.

Findings here may turn into:
- New entries in `docs/architecture/extraction/PIPELINE-LOG.md` (when prompt-tuning experiments produce real bake-off result deltas)
- New tasks in `.claude/pdf-lab-studio-queue.md` (when a finding implies missing studio capability)
- Bug fixes to `lib/extract/` (after PROMOTE-EXTRACT) or `ehi-atlas/ehi_atlas/extract/` (today)

## Quick starter — run our parser against an input PDF

```python
# pdf-review/scripts/extract_one.py (write the real one when needed)
from ehi_atlas.extract.pipelines import get as get_pipeline
from pathlib import Path
import json

source = "cedars-myhealth"
stem = "2025-11-29-myhealth"

pdf = Path(f"pdf-review/{source}/inputs/{stem}.pdf")
out = Path(f"pdf-review/{source}/our-output/{stem}.bundle.json")

pipeline = get_pipeline("multipass-fhir")
bundle = pipeline.extract(pdf)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(bundle, indent=2))
print(f"wrote {out} with {len(bundle.get('entry', []))} entries")
```

(Path becomes `lib.extract.pipelines` after `PROMOTE-EXTRACT` ships.)
