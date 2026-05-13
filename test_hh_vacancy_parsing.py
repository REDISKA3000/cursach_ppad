from app.services.mock_llm import MockLLM
from app.services.vacancy_analyzer_stage import normalize_vacancy_profile, parse_vacancy_section_text


HH_VACANCY_SAMPLE = """
Аналитик
от 150 000 ₽ за месяц, до вычета налогов
Опыт работы: 1–3 года
Полная занятость
График: 5/2
Рабочие часы: 8
Формат работы: на месте работодателя

Что мы предлагаем:

График работы: 5/2
Достойная зарплата: оклад + квартальная премия
ДМС, стоматология, страхование жизни и страхование выезжающих за рубеж после прохождения испытательного срока
Бесплатный фитнес-клуб
Льготные условия на услуги банка и компаний-партнеров
Дружный коллектив и опытный руководитель
Бесплатное обучение и широкий выбор тренингов в нашем обучающем центре

Чем предстоит заниматься:

Проводить регулярный контроль выполнения ключевых процессов
Выявлять отклонения и фиксировать их в системе мониторинга
Анализировать потоки данных и события в системе мониторинга
Отслеживать аномалии в реальном времени, и выполнять действия для возможного устранения
Вести эскалацию
Коммуницировать с операционными подразделениями и представителями ИТ

Наши пожелания к кандидатам:

Высшее образование
Уверенное пользование компьютером
Навык управления инцидентами и процессами эскалации
Знание систем мониторинга ( Grafana, Click house)
Уметь управлять инцидентами и процессами эскалации
"""


def has_fragment(items, fragment: str) -> bool:
    fragment = fragment.lower()
    return any(fragment in item.lower() for item in items)


def main():
    profile = MockLLM().parse_vacancy_profile(HH_VACANCY_SAMPLE)
    section_response = """
[ROLE]
Аналитик

[SENIORITY]
Middle

[INDUSTRY]
Banking

[MUST_HAVE]
- Высшее образование
- Уверенное пользование компьютером
- Управление инцидентами и процессами эскалации
- Системы мониторинга: Grafana, ClickHouse

[NICE_TO_HAVE]

[RESPONSIBILITIES]
- Проводить регулярный контроль выполнения ключевых процессов
- Выявлять отклонения и фиксировать их в системе мониторинга
- Анализировать потоки данных и события в системе мониторинга
- Вести эскалацию

[ATS_KEYWORDS]
Аналитик; мониторинг; Grafana; ClickHouse; управление инцидентами; эскалация; данные

[WARNINGS]
"""
    section_profile = normalize_vacancy_profile(
        parse_vacancy_section_text(section_response),
        HH_VACANCY_SAMPLE,
    )

    checks = {
        "role parsed": profile.role == "Аналитик",
        "seniority parsed": profile.seniority == "Middle",
        "industry parsed": profile.industry == "Banking",
        "must-have count": len(profile.must_have_skills) >= 6,
        "grafana parsed": has_fragment(profile.must_have_skills, "grafana"),
        "clickhouse parsed": has_fragment(profile.must_have_skills, "click house"),
        "monitoring parsed": has_fragment(profile.must_have_skills, "мониторинг"),
        "incident management parsed": has_fragment(profile.must_have_skills, "инцидент"),
        "responsibilities parsed": len(profile.key_responsibilities) == 6,
        "ats keywords parsed": has_fragment(profile.keywords_for_ats, "эскала"),
        "section role parsed": section_profile.role == "Аналитик",
        "section json-free must-have parsed": has_fragment(section_profile.must_have_skills, "grafana"),
        "section responsibilities parsed": len(section_profile.key_responsibilities) == 4,
    }

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit(f"Failed checks: {failed}")

    print("hh vacancy parsing checks passed")


if __name__ == "__main__":
    main()
