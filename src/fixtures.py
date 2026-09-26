"""Load the eight versioned, locally materialized frozen fixtures."""

import hashlib
import json
from typing import Any

from .models import JsonObject, PROJECT_ROOT


FIXTURES_DIR = PROJECT_ROOT / "fixtures"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_catalog() -> JsonObject:
    return json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))


def load_fixture(fixture_id: str) -> JsonObject:
    catalog = load_catalog()["fixtures"]
    if fixture_id not in catalog:
        raise ValueError(f"Unknown frozen fixture: {fixture_id}")
    return json.loads((FIXTURES_DIR / "semantic" / f"{fixture_id}.json")
                      .read_text(encoding="utf-8"))


def fixture_identity_valid(fixture: JsonObject) -> bool:
    fixture_id = fixture.get("fixture_id")
    if not isinstance(fixture_id, str):
        return False
    try:
        entry = load_catalog()["fixtures"].get(fixture_id)
        if entry is None or fixture.get("version") != entry["version"]:
            return False
        return content_hash(fixture) == entry["fixture_hash"]
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        # A broken catalog leaves fixture identity unverified.
        return False
