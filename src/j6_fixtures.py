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


def load_j6_fixture(fixture_id: str) -> JsonObject:
    catalog = load_j6_catalog()["fixtures"]

    if fixture_id not in catalog:
        raise ValueError(f"Unknown frozen J6 fixture: {fixture_id}")

    fixture = json.loads(
        (J6_PERMISSION_DIR / f"{fixture_id}.json").read_text(encoding="utf-8")
    )

    # Selection integrity: the requested scenario must match the identity
    # declared by the payload loaded from that scenario's path.
    if fixture.get("fixture_id") != fixture_id:
        raise ValueError(
            "Requested/payload J6 fixture identity mismatch: "
            f"requested={fixture_id!r}, payload={fixture.get('fixture_id')!r}"
        )

    entry = catalog[fixture_id]

    if fixture.get("version") != entry.get("version"):
        raise ValueError(f"Frozen J6 fixture version mismatch: {fixture_id}")

    if not j6_specification_identity_valid():
        raise ValueError("Frozen J6 specification identity is invalid")

    if content_hash(fixture) != entry.get("fixture_hash"):
        raise ValueError(f"Frozen J6 fixture content hash mismatch: {fixture_id}")

    return fixture


def j6_fixture_identity_valid(
    fixture: JsonObject,
    *,
    expected_fixture_id: str | None = None,
) -> bool:
    payload_fixture_id = fixture.get("fixture_id")

    if not isinstance(payload_fixture_id, str):
        return False

    selected_fixture_id = (
        expected_fixture_id
        if expected_fixture_id is not None
        else payload_fixture_id
    )

    # When a caller has a selected/requested identity, bind validation to it.
    if (
        expected_fixture_id is not None
        and payload_fixture_id != expected_fixture_id
    ):
        return False

    try:
        catalog = load_j6_catalog()

        entry = catalog["fixtures"].get(selected_fixture_id)
        if entry is None:
            return False

        if fixture.get("version") != entry["version"]:
            return False

        if not j6_specification_identity_valid():
            return False

        return content_hash(fixture) == entry["fixture_hash"]

    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False