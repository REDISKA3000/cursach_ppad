from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import SessionLocal
from app.services.role_relevance_pipeline import export_role_relevance_result, run_role_relevance_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run target role relevance retrieval/reranking MVP.")
    parser.add_argument("--target-role", default="Продуктовый аналитик")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument(
        "--use-llm-reranker",
        action="store_true",
        help="Try LLM reranker when OPENAI_ENABLED=true; otherwise rule-based fallback is used.",
    )
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "outputs"))
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    db = SessionLocal()
    try:
        result = run_role_relevance_pipeline(
            db,
            target_role=args.target_role,
            limit=args.limit,
            use_llm_reranker=args.use_llm_reranker,
        )
        json_path, xlsx_path = export_role_relevance_result(result, output_dir=args.output_dir)
    finally:
        db.close()

    print("Pipeline completed")
    print(result.stats.model_dump())
    print(f"JSON: {json_path}")
    print(f"XLSX: {xlsx_path}")


if __name__ == "__main__":
    main()
