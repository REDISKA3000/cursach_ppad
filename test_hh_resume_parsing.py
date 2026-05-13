from app.services.mock_llm import MockLLM


HH_RESUME_SAMPLE = """
Гладилин Егор Вячеславович
Мужчина, 22 года, родился 19 августа 2003
Желаемая должность и зарплата
Аналитик данных
Специализации:
— BI-аналитик, аналитик данных
130 000 ₽ на руки
Опыт работы — 2 года 8 месяцев
Октябрь 2024 —
настоящее время
1 год 7 месяцев
Совкомбанк Лизинг
Москва, www.sovcombank.ru
Финансовый сектор
• Банк
Риск аналитик
-Проводил регулярную портфельную аналитику кредитного портфеля.
-Сегментировал заемщиков и портфель по риск-профилю.
-Разработал и внедрил PD/LGD-модели как основу для risk-based управления портфелем.
-Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI.
Февраль 2024 —
Октябрь 2024
9 месяцев
М.Видео-Эльдорадо
Москва
Электроника, приборостроение, бытовая техника, компьютеры и оргтехника
• Бытовая техника, электроника, климатическое оборудование
Розничная торговля
• Розничная сеть
• Интернет-магазин
Продуктовый аналитик
- Разработал BI-аналитику с помощью Tableau для проектов по работе с клиентами.
- Провел разработку метрик, пользовательских историй и функциональных требований для M.Agent.
- Автоматизировал процессы рассылки приглашений в проект.
- Проектировал ETL-процессы с использованием Apache Airflow и Python.
Сентябрь 2023 —
Май 2024
9 месяцев
Бюро UP
Москва
Продуктовый аналитик
- Участвовал в разработке системы аналитики новостных трендов.
- Разработал процесс сбора данных и реализовал парсеры для Telegram и Яндекс Дзен.
- Организовал Hadoop-кластер для хранения больших объемов данных.
- Настроил фронт-аналитику системы в Google Analytics.
- Работал над A/B-тестированием новых фичей.
Образование
2025
Бакалавр
Национальный исследовательский университет «Высшая школа экономики», Москва
Факультет компьютерных наук, Прикладная математика и информатика
2025
Неоконченное
высшее
London School of Economics
Data Science and Business Analytics
Навыки
Знание языков Русский — Родной
Английский — B2 — Средне-продвинутый
Навыки  SQL      Python      Power BI      Tableau      BPMN
 Data Analysis      PostgreSQL      A/B тесты      Greenplum
 Google Analytics      DataLens      MS Excel      MySQL      Atlassian Jira
"""


def main():
    llm = MockLLM()
    profile = llm.parse_candidate_profile(HH_RESUME_SAMPLE)

    checks = {
        "target role extracted": profile.target_role == "Аналитик данных",
        "experience extracted": profile.experience_years == 2,
        "three jobs extracted": len(profile.jobs) == 3,
        "first company extracted": profile.jobs[0].company_name == "Совкомбанк Лизинг",
        "first position extracted": profile.jobs[0].position == "Риск аналитик",
        "second position extracted": profile.jobs[1].position == "Продуктовый аналитик",
        "sql parsed": "SQL" in profile.skills_hard,
        "power bi parsed": "Power BI" in profile.skills_hard,
        "google analytics parsed": "Google Analytics" in profile.skills_hard,
        "languages parsed": profile.languages == ["Русский", "Английский"],
        "education parsed": len(profile.education) >= 2,
    }

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit(f"Failed checks: {failed}")

    print("hh resume parsing checks passed")


if __name__ == "__main__":
    main()
