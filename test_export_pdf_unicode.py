#!/usr/bin/env python3
"""Regression test for Cyrillic-safe PDF export."""

import sys

sys.path.insert(0, "/Users/egorgladilin/vscodeProjects/curshad_ppad")

from app.schemas.resume import GeneratedResume, TechnicalReport
from app.services.export_service import ExportService


def main() -> int:
    generated = GeneratedResume(
        title="Резюме для Аналитик",
        resume_text="\n".join(
            [
                "======================================================================",
                "ПРОФЕССИОНАЛЬНОЕ РЕЗЮМЕ",
                "======================================================================",
                "",
                "ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ",
                "Аналитик данных с опытом 2 года(лет).",
                "",
                "КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ",
                "• Power BI, SQL, Python",
                "",
                "РЕЛЕВАНТНЫЙ ОПЫТ",
                "Риск аналитик",
                "Компания: Совкомбанк Лизинг",
            ]
        ),
        technical_report=TechnicalReport(),
    )

    pdf_bytes = ExportService.export_pdf(generated)
    assert pdf_bytes.startswith(b"%PDF")
    assert b"ArialUnicodeMS" in pdf_bytes
    assert b"/Subtype /TrueType" in pdf_bytes
    assert len(pdf_bytes) > 15_000

    print("pdf unicode export checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
