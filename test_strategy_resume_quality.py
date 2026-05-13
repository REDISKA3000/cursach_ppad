#!/usr/bin/env python3
"""Regression checks for strategy quality and non-trivial resume adaptation."""

import sys

sys.path.insert(0, "/Users/egorgladilin/vscodeProjects/curshad_ppad")

from app.agents.career_strategy_agent import CareerStrategyAgent
from app.agents.resume_writer_critic_agent import ResumeWriterCriticAgent
from app.schemas.candidate import CandidateJob, CandidateProfile, EducationItem
from app.schemas.vacancy import VacancyProfile


def build_candidate() -> CandidateProfile:
    return CandidateProfile(
        target_role="Аналитик данных",
        experience_years=2,
        jobs=[
            CandidateJob(
                id=1,
                company_name="Совкомбанк Лизинг",
                position="Риск аналитик",
                period="Октябрь 2024 — настоящее время (1 год 7 месяцев)",
                responsibilities=[
                    "Проводил регулярную портфельную аналитику кредитного портфеля: NPL, recovery rate, vintage/roll-rate анализ, динамика просрочки и эффектов реструктуризации в разрезе продуктов и сегментов клиентов.",
                    "Сегментировал заемщиков и портфель по риск-профилю, продуктам и каналам; выделял кластеры повышенного риска и драйверы дефолтов, формулировал рекомендации по cut-off, лимитам и стратегиям взыскания.",
                    "Разработал и внедрил PD/LGD-модели как основу для risk-based управления портфелем (аппрув/деклайн, лимитирование, ценообразование); интегрировал их в систему принятия решений.",
                    "Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI для оперативного отслеживания NPL, просрочки, эффективности реструктуризации и изменений качества портфеля по сегментам.",
                ],
            ),
            CandidateJob(
                id=2,
                company_name="М.Видео-Эльдорадо",
                position="Продуктовый аналитик",
                period="Февраль 2024 — Октябрь 2024 (9 месяцев)",
                responsibilities=[
                    "Разработал BI-аналитику с помощью Tableau для проектов по работе с клиентами: информационные панели NPS и CSI в сотрудничестве с командой NLP, которые помогли проанализировать проблемы на пути клиента.",
                    "Провел разработку метрик, пользовательских историй и функциональных требований для M.Agent, включая разработку сценариев анкетирования в нотации BPMN и функций для проекта на веб-сайте.",
                    "Автоматизировал процессы рассылки приглашений в проект, сформулировав требования к набору данных в Greenplum совместно с командой инженеров данных, что позволило построить воронку конверсий.",
                    "Проектировал ETL-процессы с использованием Apache Airflow и Python для автоматизации работы таблиц в БД.",
                ],
            ),
            CandidateJob(
                id=3,
                company_name="Бюро UP",
                position="Продуктовый аналитик",
                period="Сентябрь 2023 — Май 2024 (9 месяцев)",
                responsibilities=[
                    "Участвовал в разработке системы аналитики новостных трендов для маркетингового агентства, работая совместно с командой ML-инженеров.",
                    "Разработал процесс сбора данных, предложив и реализовав парсеры для Telegram и Яндекс Дзен.",
                    "Организовал Hadoop-кластер для хранения больших объемов данных и подготовил витрину данных для дообучения моделей машинного обучения.",
                    "Работал над A/B-тестированием новых фичей, анализировал влияние изменений на пользовательский опыт и KPI проекта.",
                ],
            ),
        ],
        skills_hard=[
            "SQL",
            "Python",
            "Power BI",
            "Tableau",
            "BPMN",
            "Greenplum",
            "Google Analytics",
            "A/B-тестирование",
            "Продуктовая аналитика",
            "Анализ рисков",
        ],
        education=[
            EducationItem(
                institution="Национальный исследовательский университет «Высшая школа экономики», Москва",
                degree="Бакалавр, Факультет компьютерных наук, Прикладная математика и информатика",
                year="2025",
            )
        ],
        languages=["Русский", "Английский"],
    )


def build_vacancy() -> VacancyProfile:
    return VacancyProfile(
        role="Аналитик",
        seniority="Middle",
        industry="Banking",
        must_have_skills=[
            "Высшее образование",
            "Уверенное пользование компьютером",
            "Управление инцидентами",
            "Процессы эскалации",
            "Grafana",
            "ClickHouse",
            "Системы мониторинга",
        ],
        key_responsibilities=[
            "Проводить регулярный контроль выполнения ключевых процессов",
            "Выявлять отклонения и фиксировать их в системе мониторинга",
            "Анализировать потоки данных и события в системе мониторинга",
            "Отслеживать аномалии в реальном времени, и выполнять действия для возможного устранения",
            "Вести эскалацию",
            "Коммуницировать с операционными подразделениями и представителями ИТ",
        ],
        keywords_for_ats=[
            "Аналитик",
            "Системы мониторинга",
            "Мониторинг",
            "Данные",
            "Аномалии",
            "Эскалация",
        ],
    )


def main() -> int:
    candidate = build_candidate()
    vacancy = build_vacancy()

    strategy = CareerStrategyAgent().build_strategy(candidate, vacancy)
    generated = ResumeWriterCriticAgent().generate_resume(candidate, vacancy, strategy)

    checks = {
        "fit score is evidence-based": strategy.fit_score > 0.45,
        "education is not treated as gap": "Высшее образование" not in strategy.gaps,
        "monitoring is explicitly highlighted": any("монитор" in skill.lower() for skill in strategy.skills_to_highlight),
        "most relevant banking role is prioritized": strategy.highlight_job_ids[:1] == [1],
        "resume contains focused profile summary": "ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ" in generated.resume_text,
        "resume includes secondary experience section": "ДОПОЛНИТЕЛЬНЫЙ ОПЫТ" in generated.resume_text,
        "resume is not full copy of all bullets": generated.resume_text.count("•") <= 8,
        "technical report covers monitoring": any("монитор" in item.lower() for item in generated.technical_report.covered_must_haves),
    }

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        for name in failed:
            print(f"FAIL: {name}")
        print()
        print(strategy.model_dump())
        print()
        print(generated.resume_text)
        return 1

    print("All strategy/resume quality checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
