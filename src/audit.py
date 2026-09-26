"""Persist complete JSON records atomically, only below local evidence/."""

import json
import os
import tempfile
from pathlib import Path
from uuid import UUID

from .models import JsonObject, PROJECT_ROOT


EVIDENCE_ROOT = PROJECT_ROOT / "evidence"


class EvidencePersistenceError(RuntimeError):
    """A computed component result is NOT COMMITTABLE without its evidence."""


class AuditWriter:
    def __init__(self, directory: Path = EVIDENCE_ROOT):
        self.directory = Path(directory)

    def write(self, record: JsonObject) -> Path:
        pending: Path | None = None
        try:
            directory = self.directory.resolve()
            if not directory.is_relative_to(EVIDENCE_ROOT):
                raise ValueError("Runtime evidence must remain under local evidence/")
            directory.mkdir(parents=True, exist_ok=True)
            if not directory.resolve().is_relative_to(EVIDENCE_ROOT):
                raise ValueError("Evidence path resolves outside local evidence/")
            decision_id = str(UUID(record["logical_decision_id"]))
            destination = directory / f"{decision_id}.json"
            if destination.exists():
                raise FileExistsError("Decision evidence already exists")
            # Pending files never have a .json suffix. Only the rename commits one.
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=directory,
                prefix=".pending-", suffix=".tmp", delete=False,
            ) as stream:
                pending = Path(stream.name)
                json.dump(record, stream, indent=2, sort_keys=True,
                          ensure_ascii=False, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, destination)
            return destination
        except Exception as error:
            cleanup_detail = ""
            if pending is not None:
                try:
                    pending.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    cleanup_detail = f"; pending-file cleanup failed: {cleanup_error}"
            raise EvidencePersistenceError(
                f"NOT COMMITTABLE: evidence persistence failed: {error}{cleanup_detail}"
            ) from error
