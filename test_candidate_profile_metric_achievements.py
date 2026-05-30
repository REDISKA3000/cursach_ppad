#!/usr/bin/env python3
"""Regression check: CandidateProfile must not lose quantified career signals."""

import json
import sys

sys.path.insert(0, "/Users/egorgladilin/vscodeProjects/curshad_ppad")

from app.services.candidate_profile_stage import normalize_candidate_profile, parse_candidate_profile_section_text


RESUME_TEXT = """АО АльфаБанк
фев.2025 – н.в.
Продуктовый аналитик
Анализ и составление метрик для 7 продуктовых команд Альфа Инвестиции (70 000+ DAU). Генерация продуктовых гипотез, выполнение A/B тестирования креативов. Увеличение конверсии воронки открытия инвестиционного счёта на 10%. Выполнение Ad-Hoc аналитики.
"""


LOSSY_LLM_OUTPUT = """[TARGET_ROLE]
Продуктовый аналитик

[EXPERIENCE_MONTHS]
5

[EXPERIENCE_RAW]
фев.2025 – н.в.

[SUMMARY_RAW]

[JOB_1]
company: АО АльфаБанк
company_type: bank / financial sector
position: Продуктовый аналитик
period: фев.2025 – н.в.
highlights:
- Анализ продуктовых метрик

[SKILLS_HARD]
SQL; продуктовая аналитика

[SKILLS_SOFT]

[EDUCATION]

[LANGUAGES]

[CERTIFICATIONS]

[ACHIEVEMENTS]

[AMBIGUITIES]

[WARNINGS]
"""


def main() -> None:
    profile = parse_candidate_profile_section_text(LOSSY_LLM_OUTPUT)
    profile = normalize_candidate_profile(profile, RESUME_TEXT)
    serialized = json.dumps(profile.model_dump(mode="json"), ensure_ascii=False).lower()

    assert "конверсии воронки" in serialized
    assert "10%" in serialized
    assert "70 000" in serialized or "70000" in serialized
    assert "a/b" in serialized or "а/b" in serialized
    assert "гипотез" in serialized
    assert any(item.source == "regex_metric_scan" for item in profile.achievements)

    print("candidate profile metric achievement checks passed")


if __name__ == "__main__":
    main()
