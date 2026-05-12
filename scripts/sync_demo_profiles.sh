#!/usr/bin/env bash
#
# Sync the gitignored heavy patient source data under data/demo-profiles/
# to a remote host (the Mac mini server, in practice).
#
# What this syncs (the bulky raw artefacts that are NOT in git):
#   - icu-mimic/raw/                              (50 MB MIMIC distribution)
#   - icu-mimic/*.zip                             (49 MB original PhysioNet archive)
#   - icu-mimic/fhir/*.json                       (45 MB assembled patient slice)
#   - cardiac-coherent/fhir/*.json                (34 MB Coherent FHIR)
#   - cardiac-coherent/imaging/*.dcm              (33 MB DICOM)
#   - polypharmacy-synthea/fhir/*.json            (16 MB Ester635 bundle)
#
# What is NOT synced by this script (already in git):
#   - All synthetic documents (PDF, C-CDA XML, supplemental FHIR Bundles)
#   - All README.md and sources.md files
#   - The mCODE Jenny M bundle (small, committed)
#   - Brady998's DNA file (small, committed)
#   - scripts/
#
# Usage:
#   scripts/sync_demo_profiles.sh push                  # local → mac mini
#   scripts/sync_demo_profiles.sh pull                  # mac mini → local
#   REMOTE=user@host:/path scripts/sync_demo_profiles.sh push
#
# Defaults can be overridden via env vars:
#   REMOTE      ssh target + path (default: macmini:/Volumes/data/ehi-demo-profiles)
#   LOCAL       local dir (default: data/demo-profiles relative to repo root)

set -euo pipefail

REMOTE="${REMOTE:-macmini:/Volumes/data/ehi-demo-profiles}"
LOCAL="${LOCAL:-data/demo-profiles}"

# Trailing slash on the source matters for rsync — it copies *contents*.
SRC="${LOCAL%/}/"
DST="${REMOTE%/}/"

cd "$(git rev-parse --show-toplevel)"

# Only sync the heavy items. Use --include to whitelist, --exclude '*' at the end
# to drop everything else. Trailing slash on dir patterns matches the dir.
RSYNC_FILTERS=(
  # heavy MIMIC bits
  "--include=icu-mimic/"
  "--include=icu-mimic/raw/"
  "--include=icu-mimic/raw/**"
  "--include=icu-mimic/*.zip"
  "--include=icu-mimic/fhir/"
  "--include=icu-mimic/fhir/*.json"
  # Coherent FHIR + DICOM
  "--include=cardiac-coherent/"
  "--include=cardiac-coherent/fhir/"
  "--include=cardiac-coherent/fhir/*.json"
  "--include=cardiac-coherent/imaging/"
  "--include=cardiac-coherent/imaging/*.dcm"
  # Ester635 FHIR bundle
  "--include=polypharmacy-synthea/"
  "--include=polypharmacy-synthea/fhir/"
  "--include=polypharmacy-synthea/fhir/*.json"
  # exclude everything else (the git-tracked stuff)
  "--exclude=*"
)

CMD=(rsync -avh --progress "${RSYNC_FILTERS[@]}")

case "${1:-}" in
  push)
    echo "→ pushing heavy demo-profile data: $SRC  →  $DST"
    "${CMD[@]}" "$SRC" "$DST"
    ;;
  pull)
    echo "← pulling heavy demo-profile data: $DST  →  $SRC"
    "${CMD[@]}" "$DST" "$SRC"
    ;;
  *)
    echo "usage: $0 {push|pull}" >&2
    echo ""
    echo "Heavy demo-profile data (~228 MB) is gitignored and synced manually."
    echo "Configure REMOTE env var or edit the default at the top of this script."
    echo ""
    echo "current REMOTE: $REMOTE"
    echo "current LOCAL:  $LOCAL"
    exit 2
    ;;
esac
