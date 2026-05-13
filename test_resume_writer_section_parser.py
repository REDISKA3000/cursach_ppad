#!/usr/bin/env python3
"""Regression checks for section-based ResumeWriter/Critic parsing."""

import sys

sys.path.insert(0, "/Users/egorgladilin/vscodeProjects/curshad_ppad")

from app.services.resume_writer_stage import (
    build_rule_based_technical_report,
    finalize_generated_resume,
    parse_resume_critic_section_text,
    parse_resume_writer_section_text,
)
from test_strategy_resume_quality import build_candidate, build_vacancy
from app.schemas.strategy import StrategyBrief


WRITER_OUTPUT = """
[TITLE]
Резюме для Аналитик

[SUMMARY]
Аналитик данных с опытом в банковской риск-аналитике, портфельном мониторинге и risk-based decisioning. Фокус под вакансию: банковская риск-отчетность и мониторинг, портфельная риск-аналитика, PD/LGD.

[KEY_SKILLS]
- Системы мониторинга
- Анализ рисков
- Power BI
- Tableau

[RELEVANT_EXPERIENCE]
### Job 1
Риск аналитик
Компания: Совкомбанк Лизинг
Период: Октябрь 2024 — настоящее время (1 год 7 месяцев)
- Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI для оперативного отслеживания NPL, просрочки, эффективности реструктуризации и изменений качества портфеля по сегментам.
- Разработал и внедрил PD/LGD-модели как основу для risk-based управления портфелем.
Продуктовый аналитик — М.Видео-Эльдорадо
Февраль 2024 — Октябрь 2024 (9 месяцев)
- Автоматизировал процессы рассылки приглашений в проект, сформулировав требования к набору данных в Greenplum совместно с командой инженеров данных.

[ADDITIONAL_EXPERIENCE]
- Продуктовый аналитик | Бюро UP | Сентябрь 2023 — Май 2024 (9 месяцев): аналитика новостных трендов.

[EDUCATION]
- Национальный исследовательский университет «Высшая школа экономики», Москва | Бакалавр | 2025

[LANGUAGES]
- Русский
- Английский

[WARNINGS]
- Grafana и ClickHouse не указаны в профиле кандидата.
"""


CRITIC_OUTPUT = """
[COVERED_MUST_HAVES]
- Высшее образование
- Системы мониторинга

[UNCOVERED_MUST_HAVES]
- Grafana
- ClickHouse

[USED_ACHIEVEMENT_HIGHLIGHTS]
- Настроил систему мониторинга кредитного риска
- Разработал и внедрил PD/LGD-модели

[USED_PRIORITY_THEMES]
- банковская риск-отчетность и мониторинг
- портфельная риск-аналитика

[OMITTED_STRATEGY_ITEMS]
- Процессы эскалации

[HALLUCINATION_CHECKS]
- Не найдено явных выдуманных компаний или дат

[WARNINGS]
- Не закрыты Grafana и ClickHouse

[CONFIDENCE]
medium
"""


def main() -> int:
    candidate = build_candidate()
    vacancy = build_vacancy()
    strategy = StrategyBrief(
        positioning="Аналитик данных под банковский мониторинг рисков",
        highlight_job_ids=[1, 2],
        downplay_job_ids=[3],
        skills_to_highlight=["Системы мониторинга", "Анализ рисков", "Power BI", "Tableau"],
        achievement_highlights=[
            "Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI для оперативного отслеживания NPL, просрочки, эффективности реструктуризации и изменений качества портфеля по сегментам.",
            "Разработал и внедрил PD/LGD-модели как основу для risk-based управления портфелем.",
        ],
        priority_themes=["банковская риск-отчетность и мониторинг", "портфельная риск-аналитика", "PD/LGD и risk-based decisioning"],
        gaps=["Grafana", "ClickHouse"],
    )

    generated, writer_warnings, writer_sections = parse_resume_writer_section_text(WRITER_OUTPUT)
    critic, critic_sections = parse_resume_critic_section_text(CRITIC_OUTPUT)
    generated = finalize_generated_resume(
        generated,
        candidate,
        vacancy,
        strategy,
        writer_warnings,
        critic_report=critic,
    )
    malformed_report = build_rule_based_technical_report(
        candidate,
        vacancy,
        strategy,
        "РЕЛЕВАНТНЫЙ ОПЫТ\n• Февраль 2024 — Октябрь 2024\n• Чужой bullet без заголовка\n",
    )

    checks = {
        "writer sections parsed": writer_sections >= 7,
        "critic sections parsed": critic_sections >= 7,
        "achievement appears in final text": "PD/LGD" in generated.resume_text,
        "priority theme appears in final text": "портфельная риск-аналитика" in generated.resume_text,
        "technical job markers removed": "### Job" not in generated.resume_text and "Компания:" not in generated.resume_text and "Период:" not in generated.resume_text,
        "second highlighted job is separate block": "\n\nПродуктовый аналитик — М.Видео-Эльдорадо\nФевраль 2024" in generated.resume_text,
        "second job bullet follows second job heading": generated.resume_text.find("Продуктовый аналитик — М.Видео-Эльдорадо") < generated.resume_text.find("Автоматизировал процессы рассылки"),
        "period is not rendered as bullet": "• Февраль 2024" not in generated.resume_text and "• Октябрь 2024" not in generated.resume_text,
        "side-domain skills removed": "Продуктовая аналитика" not in generated.resume_text and "A/B" not in generated.resume_text,
        "technical report uses achievements": bool(generated.technical_report.used_achievement_highlights),
        "technical report has hallucination checks": bool(generated.technical_report.hallucination_checks),
        "critic catches malformed job structure": any("структура блоков опыта" in warning for warning in malformed_report.critic_warnings),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        for name in failed:
            print(f"FAIL: {name}")
        print(generated.model_dump())
        return 1

    print("ResumeWriter/Critic section parser checks passed.")
    print(generated.model_dump())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
