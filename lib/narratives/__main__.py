"""CLI: ``python -m lib.narratives <patient_id>``.

Regenerates every episode narrative for the given patient using the
default Sonnet backend. Exits non-zero if anything fails.

Acceptance for T5 (LLM-CONTEXT-AUGMENTATION-PLAN.md §T5):

    Running `python -m lib.narratives <patient_id>` produces two
    current.json files (one per seed episode)...

Note: requires ANTHROPIC_API_KEY in the environment for the real LLM
call. Pass ``--fake`` to use the deterministic ``FakeNarrativeGenerator``
for smoke-testing without spending tokens.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patient_id", help="Patient identifier (Synthea filename stem or UUID)")
    parser.add_argument(
        "--collection-id",
        default=None,
        help=(
            "Override the harmonize collection id. Defaults to "
            "workspace-<patient_id>; falls back to the raw Synthea "
            "bundle if no workspace exists."
        ),
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use FakeNarrativeGenerator instead of Sonnet (no LLM cost).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging."
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    from api.core.narrative_service import regenerate_all_episodes
    from lib.narratives import FakeNarrativeGenerator

    generator = FakeNarrativeGenerator() if args.fake else None
    written = regenerate_all_episodes(
        args.patient_id,
        collection_id=args.collection_id,
        generator=generator,
    )
    if not written:
        print(f"no narratives written for {args.patient_id}", file=sys.stderr)
        return 1
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
