#!/usr/bin/env bash
# validate-privacy-gate.sh
#
# Fail the build if any personal raw data has been staged for commit.
# Invoked by `make validate-gate` and as a pre-commit hook.

set -euo pipefail

ATLAS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ATLAS_ROOT"

# Personal sources whose raw/ directories must never be committed.
PERSONAL_SOURCES=(
    "corpus/_sources/blake-cedars/raw"
    "corpus/_sources/devon-cedars/raw"
    "corpus/_sources/cedars-portal-pdfs/raw"
)

# Tier directories that should never be committed (reproducible from sources).
TIER_DIRS=(
    "corpus/bronze"
    "corpus/silver"
    "corpus/gold"
)

violations=0

# Check personal sources
for src in "${PERSONAL_SOURCES[@]}"; do
    if [[ -d "$src" ]]; then
        # Anything in raw/ that isn't gitignored is a violation
        if git ls-files --error-unmatch "$src/" >/dev/null 2>&1; then
            tracked=$(git ls-files "$src/" 2>/dev/null || true)
            if [[ -n "$tracked" ]]; then
                echo "❌ PRIVACY VIOLATION: tracked files in $src/" >&2
                echo "$tracked" >&2
                violations=$((violations + 1))
            fi
        fi
    fi
done

# Check tier directories
for tier in "${TIER_DIRS[@]}"; do
    if [[ -d "$tier" ]]; then
        tracked=$(git ls-files "$tier/" 2>/dev/null || true)
        if [[ -n "$tracked" ]]; then
            echo "❌ TIER VIOLATION: tracked files in $tier/ (should be reproducible, not committed)" >&2
            echo "$tracked" | head -10 >&2
            violations=$((violations + 1))
        fi
    fi
done

# Check that redacted files have the redaction marker
for src_dir in corpus/_sources/blake-cedars/raw-redacted corpus/_sources/devon-cedars/raw-redacted corpus/_sources/cedars-portal-pdfs/raw-redacted; do
    if [[ -d "$src_dir" ]]; then
        find "$src_dir" -type f \( -name "*.json" -o -name "*.txt" -o -name "*.md" \) 2>/dev/null | while read -r f; do
            if ! grep -qE "(REDACTED via|redaction-profile:)" "$f" 2>/dev/null; then
                echo "⚠  WARNING: $f lacks redaction marker (expected '# REDACTED via <profile>' or 'redaction-profile:' field)" >&2
                # warning, not violation, since we may have non-text redacted files
            fi
        done
    fi
done

if (( violations > 0 )); then
    echo "" >&2
    echo "Privacy gate FAILED with $violations violation(s)." >&2
    echo "Personal raw data and tier outputs must never be committed." >&2
    echo "See ehi-atlas/.gitignore and docs/ADAPTER-CONTRACT.md §Privacy gate." >&2
    exit 1
fi

echo "✓ privacy gate clean"
exit 0
