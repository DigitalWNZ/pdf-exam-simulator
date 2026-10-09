"""Bank discovery and atomic progress persistence (data/progress/<bank_id>.json)."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

BANK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
IMAGE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
PROGRESS_VERSION = 1


class InvalidBankId(ValueError):
    pass


class BankNotFound(KeyError):
    pass


def default_progress(bank_id: str) -> dict:
    return {"version": PROGRESS_VERSION, "bank_id": bank_id, "updated_at": None,
            "questions": {}, "exams": [], "active_exam": None, "practice": None}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write_json(path: Path, doc: dict) -> None:
    """Write to <name>.tmp in the same directory, fsync, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class Storage:
    def __init__(self, banks_dir: Path, data_dir: Path):
        self.banks_dir = Path(banks_dir).resolve()
        self.progress_dir = (Path(data_dir) / "progress").resolve()

    # --- banks ---
    def check_id(self, bank_id: str) -> str:
        if not BANK_ID_RE.match(bank_id or ""):
            raise InvalidBankId(bank_id)
        return bank_id

    def bank_dir(self, bank_id: str) -> Path:
        path = (self.banks_dir / self.check_id(bank_id)).resolve()
        if path.parent != self.banks_dir:
            raise InvalidBankId(bank_id)
        return path

    def bank_file(self, bank_id: str) -> Path:
        path = self.bank_dir(bank_id) / "questions.json"
        if not path.is_file():
            raise BankNotFound(bank_id)
        return path

    def list_banks(self) -> list[dict]:
        banks = []
        if self.banks_dir.is_dir():
            for qfile in sorted(self.banks_dir.glob("*/questions.json")):
                try:
                    meta = json.loads(qfile.read_text(encoding="utf-8"))["bank"]
                    banks.append({"id": meta["id"], "title": meta["title"], "question_count": meta["question_count"]})
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    log.warning("skipping unreadable bank %s: %s", qfile, exc)
        return sorted(banks, key=lambda b: str(b["title"]).lower())

    def load_bank(self, bank_id: str) -> dict:
        return json.loads(self.bank_file(bank_id).read_text(encoding="utf-8"))

    def image_path(self, bank_id: str, filename: str) -> Path:
        if not IMAGE_NAME_RE.match(filename or ""):
            raise BankNotFound(filename)
        path = self.bank_dir(bank_id) / "images" / filename
        if not path.is_file():
            raise BankNotFound(filename)
        return path

    # --- progress ---
    def progress_path(self, bank_id: str) -> Path:
        return self.progress_dir / f"{self.check_id(bank_id)}.json"

    def load_progress(self, bank_id: str) -> dict:
        self.bank_file(bank_id)                      # unknown bank → BankNotFound
        path = self.progress_path(bank_id)
        if not path.exists():
            return default_progress(bank_id)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                raise ValueError("progress root is not an object")
            return doc
        except (ValueError, UnicodeDecodeError) as exc:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = path.with_name(f"{path.name}.corrupt-{stamp}")
            path.rename(backup)
            log.warning("corrupt progress for %s moved to %s (%s)", bank_id, backup.name, exc)
            return default_progress(bank_id)

    def save_progress(self, bank_id: str, doc: dict) -> dict:
        self.bank_file(bank_id)
        if not isinstance(doc, dict) or doc.get("version") != PROGRESS_VERSION or doc.get("bank_id") != bank_id:
            raise ValueError("progress document must be an object with version 1 and a matching bank_id")
        saved = dict(doc)
        saved["updated_at"] = utc_now()
        atomic_write_json(self.progress_path(bank_id), saved)
        return saved
