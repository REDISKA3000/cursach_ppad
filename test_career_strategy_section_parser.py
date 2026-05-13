#!/usr/bin/env python3
"""Regression checks for section-based LLM-first CareerStrategy parsing."""

import sys

sys.path.insert(0, "/Users/egorgladilin/vscodeProjects/curshad_ppad")

from app.services.career_strategy_stage import parse_career_strategy_section_text
from test_strategy_resume_quality import build_candidate, build_vacancy


RAW_STRATEGY = """
[POSITIONING]
Риск-аналитик с сильным фокусом на мониторинг кредитного риска и банковскую аналитику.

[QUALITATIVE_FIT]
high - есть релевантный банковский риск-опыт и мониторинг, но нет Grafana.

[HIGHLIGHT_JOBS]
1, 2

[DOWNPLAY_JOBS]
3

[SKILLS_TO_HIGHLIGHT]
Системы мониторинга; Анализ рисков; Power BI; Tableau

[SKILLS_TO_SOFTEN]
Google Analytics

[ACHIEVEMENT_HIGHLIGHTS]
- Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI для оперативного отслеживания NPL, просрочки, эффективности реструктуризации и изменений качества портфеля по сегментам.
- Автоматизировал процессы рассылки приглашений в проект, сформулировав требования к набору данных в Greenplum совместно с командой инженеров данных, что позволило построить воронку конверсий.

[GAPS]
- Grafana
- Процессы эскалации

[RESUME_VARIANTS]
- Риск-аналитик под мониторинг банковских процессов
- Аналитик данных с акцентом на risk monitoring

[RECOMMENDATIONS]
Вынести наверх мониторинг кредитного риска, риск-аналитику и BI-дашборды; Grafana указать как смежный пробел.

[WARNINGS]
- Grafana не найдена в профиле кандидата.
"""


def main() -> int:
    candidate = build_candidate()
    vacancy = build_vacancy()
    strategy, parsed_count = parse_career_strategy_section_text(RAW_STRATEGY, candidate, vacancy)

    checks = {
        "sections parsed": parsed_count >= 9,
        "LLM positioning preserved": strategy.positioning.startswith("Риск-аналитик"),
        "highlight ids preserved and valid": strategy.highlight_job_ids == [1, 2],
        "new achievement highlights populated": len(strategy.achievement_highlights) >= 2,
        "qualitative fit calibrated": strategy.qualitative_fit.startswith("medium"),
        "support score attached": strategy.support_fit_score is not None,
        "fallback not used": not strategy.fallback_used,
        "confidence is usable": strategy.strategy_confidence in {"medium", "high"},
    }

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        for name in failed:
            print(f"FAIL: {name}")
        print(strategy.model_dump())
        return 1

    print("CareerStrategy section parser checks passed.")
    print(strategy.model_dump())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
