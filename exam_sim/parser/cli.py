"""parse-pdf: ExamTopics-style PDF → banks/<id>/questions.json (+ images/)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .assemble import build_question
from .bilingual import is_bilingual, parse_bilingual, read_lines
from .blocks import parse_questions
from .extract import extract_items
from .images import ImageWriter
from .model import BankMeta, bank_to_dict
from .report import Report, build_report, format_report


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:64] or "bank"


def parse_pdf(pdf_path: Path, out_dir: Path, bank_id: str, title: str,
              fmt: str = "auto") -> tuple[dict, Report]:
    bank_dir = out_dir / bank_id
    bank_dir.mkdir(parents=True, exist_ok=True)
    writer = ImageWriter(bank_dir)
    writer.reset_dir()
    if fmt == "auto":
        fmt = "bilingual" if is_bilingual(read_lines(pdf_path)) else "examtopics"
    if fmt == "bilingual":
        raws = parse_bilingual(read_lines(pdf_path))
    else:
        raws = parse_questions(extract_items(pdf_path))
    questions = [build_question(raw, writer.writer_for(raw.number)) for raw in raws]
    meta = BankMeta(id=bank_id, title=title, source_pdf=pdf_path.name,
                    parsed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    question_count=len(questions))
    doc = bank_to_dict(meta, questions)
    (bank_dir / "questions.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc, build_report(questions, raws, writer.warnings)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="parse-pdf", description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--id", dest="bank_id", help="bank id (default: slug of the PDF file name)")
    ap.add_argument("--title", help="bank title (default: PDF file name)")
    ap.add_argument("--out", type=Path, default=Path("banks"), help="output root (default: banks/)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if the report contains errors")
    ap.add_argument("--format", choices=("auto", "examtopics", "bilingual"), default="auto",
                    help="PDF layout (default: auto-detect)")
    args = ap.parse_args(argv)
    if not args.pdf.is_file():
        ap.error(f"PDF not found: {args.pdf}")
    bank_id = args.bank_id or slugify(args.pdf.stem)
    title = args.title or args.pdf.stem
    doc, report = parse_pdf(args.pdf, args.out, bank_id, title, args.format)
    print(f"wrote {args.out / bank_id / 'questions.json'} ({doc['bank']['question_count']} questions)")
    print(format_report(report))
    if args.strict and report.errors():
        print("strict mode: errors present", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
