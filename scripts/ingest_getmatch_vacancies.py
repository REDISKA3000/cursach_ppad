#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.db import SessionLocal, init_db
from app.repositories.resumes import JobBoardVacancyRepository
from app.services.vacancy_recommendations import ingest_getmatch_vacancies


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest real GetMatch vacancies into job_board_vacancies.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional test limit. Without this flag the script performs a full public GetMatch sync.",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        removed_demo_rows = JobBoardVacancyRepository.delete_known_demo_rows(db)
        before = JobBoardVacancyRepository.count(db)
        result = ingest_getmatch_vacancies(db, limit=args.limit, commit=True)
        after = JobBoardVacancyRepository.count(db)
        print(
            "total_from_api={total} discovered={discovered} saved_or_updated={saved} "
            "skipped={skipped} failed={failed} removed_demo_rows={removed_demo_rows} "
            "total_before={before} total_after={after}".format(
                total=result.total_from_api,
                discovered=result.discovered,
                saved=result.saved,
                skipped=result.skipped,
                failed=result.failed,
                removed_demo_rows=removed_demo_rows,
                before=before,
                after=after,
            )
        )
        preview_limit = min(10, args.limit or 10)
        shown = 0
        for vacancy in JobBoardVacancyRepository.list_all(db):
            if vacancy.source != "getmatch":
                continue
            description = " ".join((vacancy.description or "").split())[:140]
            print(f"{vacancy.id} | {vacancy.source} | {vacancy.title} | {vacancy.company} | {description}")
            shown += 1
            if shown >= preview_limit:
                break
    finally:
        db.close()


if __name__ == "__main__":
    main()
