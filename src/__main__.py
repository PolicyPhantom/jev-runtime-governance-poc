"""Local mock runner: python -m src --fixture F-01 --label SUFFICIENT."""

import argparse
import json
import sys

from .audit import EvidencePersistenceError
from .fixtures import load_catalog, load_fixture
from .harness import run
from .models import LABELS
from .providers import MockProvider, mock_choice


def main() -> int:
    parser = argparse.ArgumentParser(description="J3 mock-only semantic component harness")
    parser.add_argument("--fixture", choices=tuple(load_catalog()["fixtures"]), required=True)
    parser.add_argument("--label", choices=LABELS, required=True,
                        help="Explicit scripted mock answer; never inferred from fixture expectations")
    args = parser.parse_args()
    try:
        result = run(load_fixture(args.fixture), MockProvider(mock_choice(args.label)))
    except EvidencePersistenceError as error:
        print(json.dumps({"status": "NOT_COMMITTABLE", "error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps({
        "status": "EVIDENCE_PERSISTED",
        "component_outcome": result.record["component_gate"]["component_outcome"],
        "evidence_path": str(result.evidence_path),
        "scope": "SEMANTIC_CHECK_PASS is not runtime permission",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
