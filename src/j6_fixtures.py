"""Load and verify the frozen J6 permission fixtures."""

import hashlib
import json

from .fixtures import content_hash
from .models import JsonObject, PROJECT_ROOT


J6_FIXTURES_DIR = PROJECT_ROOT / "fixtures" / "j6"
J6_PERMISSION_DIR = J6_FIXTURES_DIR / "permission"

J6_SPEC_RELATIVE_PATH = "docs/Jev_PoC_J6_Specification_v0.3_20260930.md"


def load_j6_catalog() -> JsonObject:
    return json.loads(
        (J6_FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8")
    )


def load_j6_fixture(fixture_id: str) -> JsonObject:
    catalog = load_j6_catalog()["fixtures"]

    if fixture_id not in catalog:
        raise ValueError(f"Unknown frozen J6 fixture: {fixture_id}")

    return json.loads(
        (J6_PERMISSION_DIR / f"{fixture_id}.json").read_text(encoding="utf-8")
    )


def j6_specification_identity_valid() -> bool:
    try:
        catalog = load_j6_catalog()

        if catalog.get("specification_status") != "FROZEN":
            return False

        if catalog.get("specification") != J6_SPEC_RELATIVE_PATH:
            return False

        recorded_hash = catalog.get("specification_sha256")
        if not isinstance(recorded_hash, str):
            return False

        specification_path = PROJECT_ROOT / J6_SPEC_RELATIVE_PATH
        actual_hash = hashlib.sha256(specification_path.read_bytes()).hexdigest()

        return actual_hash == recorded_hash.lower()

    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def j6_fixture_identity_valid(fixture: JsonObject) -> bool:
    fixture_id = fixture.get("fixture_id")

    if not isinstance(fixture_id, str):
        return False

    try:
        catalog = load_j6_catalog()

        entry = catalog["fixtures"].get(fixture_id)
        if entry is None:
            return False

        if fixture.get("version") != entry["version"]:
            return False

        if not j6_specification_identity_valid():
            return False

        return content_hash(fixture) == entry["fixture_hash"]

    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False