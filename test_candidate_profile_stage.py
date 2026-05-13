#!/usr/bin/env python3
"""Regression checks for the upgraded CandidateProfile stage."""

import json
import sys

sys.path.insert(0, "/Users/egorgladilin/vscodeProjects/curshad_ppad")

from app.config import OPENAI_MODEL
from app.config import CANDIDATE_EVIDENCE_VALIDATION_ENABLED
from app.schemas.candidate import CandidateJob, CandidateProfile, EducationItem, LanguageItem
from app.services.candidate_profile_stage import (
    build_follow_up_questions,
    detect_resume_sections,
    normalize_candidate_profile,
)
from app.services.llm_provider import OpenAIProvider
from app.services.mock_llm import MockLLM


HH_RU_RESUME = """Аналитик данных
Опыт работы — 2 года 8 месяцев

Желаемая должность
Аналитик данных

Опыт работы
Октябрь 2024 — настоящее время
Совкомбанк Лизинг — банк, финансовый сектор
Риск аналитик
- Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI.
- Автоматизировал отчётность в SQL и Python.
- Увеличил точность риск-мониторинга на 18%.

Февраль 2024 — Октябрь 2024
М.Видео-Эльдорадо — ритейл / e-commerce
Продуктовый аналитик
- Построил воронку конверсий и увеличил conversion rate на 2.5%.
- Работал с Greenplum и Tableau.

Навыки
SQL, Python, Power BI, Tableau, Greenplum

Образование
НИУ ВШЭ
Бакалавр, Прикладная математика и информатика
2025

Языки
Русский — Родной
Английский — B2
"""


MIXED_RESUME = """Senior Product Analyst
Total experience: 4 years 3 months

Summary
Product analyst with experience across SaaS and fintech products.

Experience
2022 - Present
GrowthLoop SaaS platform
Senior Product Analyst
- Built product dashboards in Looker and SQL.
- Increased retention by 12% through cohort analysis and experiment design.
- Worked with Python and Amplitude.

2020 - 2022
Fintech mobile app
Product Analyst
- Improved fraud monitoring and reduced manual review time by 30%.

Education
Higher School of Economics
Bachelor, Applied Mathematics
2022

Languages
English — Upper-Intermediate
German (basic)

Skills
SQL, Python, Looker, Amplitude, Experiment design
"""


SHORT_RESUME = """Data Analyst
Experience: 1 year 6 months

Acme Marketing Agency
Data Analyst
2023 - 2024
Built Tableau dashboard for campaign reporting.

Skills
SQL, Tableau

Languages
English
"""


class FakeProvider(OpenAIProvider):
    def __init__(self, responses):
        self.name = "fake-openai"
        self.enabled = True
        self.fallback = MockLLM()
        self.responses = iter(responses)
        self.calls = []

    def _call_response_text(
        self,
        *,
        instructions,
        input_text,
        model,
        temperature,
        max_output_tokens,
    ):
        self.calls.append(
            {
                "temperature": temperature,
                "model": model,
                "max_output_tokens": max_output_tokens,
            }
        )
        return next(self.responses)


def _build_hh_like_profile() -> CandidateProfile:
    return CandidateProfile(
        canonical_profile={
            "target_role": "Аналитик данных",
            "experience_years": 2,
            "jobs": [
                {
                    "id": 1,
                    "company_name": "Совкомбанк Лизинг",
                    "position": "Риск аналитик",
                    "period": "Октябрь 2024 — настоящее время",
                    "responsibilities": [
                        "Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI.",
                        "Автоматизировал отчётность в SQL и Python.",
                        "Увеличил точность риск-мониторинга на 18%.",
                    ],
                    "achievements": [],
                    "skills_used": [],
                },
                {
                    "id": 2,
                    "company_name": "М.Видео-Эльдорадо",
                    "position": "Продуктовый аналитик",
                    "period": "Февраль 2024 — Октябрь 2024",
                    "responsibilities": [
                        "Построил воронку конверсий и увеличил conversion rate на 2.5%.",
                        "Работал с Greenplum и Tableau.",
                    ],
                    "achievements": [],
                    "skills_used": [],
                },
            ],
            "skills_hard": ["SQL", "sql", "Python", "Power BI", "Tableau", "Greenplum"],
            "education": [
                {"institution": "НИУ ВШЭ", "degree": "Бакалавр", "field": "Прикладная математика и информатика", "year": "2025"}
            ],
            "languages": [{"name": "Русский"}, {"name": "Английский"}],
        },
        evidence={
            "target_role": ["Аналитик данных"],
            "experience_years": ["Опыт работы — 2 года 8 месяцев"],
            "job_1_company": ["Совкомбанк Лизинг — банк, финансовый сектор"],
            "job_1_position": ["Риск аналитик"],
            "job_1_period": ["Октябрь 2024 — настоящее время"],
            "job_1_responsibilities": [
                "Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI.",
                "Автоматизировал отчётность в SQL и Python.",
            ],
            "job_1_achievements": ["Увеличил точность риск-мониторинга на 18%."],
            "job_1_skills_used": [
                "Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI.",
                "Автоматизировал отчётность в SQL и Python.",
            ],
            "job_2_company": ["М.Видео-Эльдорадо — ритейл / e-commerce"],
            "job_2_position": ["Продуктовый аналитик"],
            "job_2_period": ["Февраль 2024 — Октябрь 2024"],
            "job_2_responsibilities": ["Работал с Greenplum и Tableau."],
            "job_2_achievements": ["Построил воронку конверсий и увеличил conversion rate на 2.5%."],
            "job_2_skills_used": ["Работал с Greenplum и Tableau."],
            "skills_hard": ["SQL, Python, Power BI, Tableau, Greenplum"],
            "education": ["Бакалавр, Прикладная математика и информатика"],
            "languages": ["Русский — Родной", "Английский — B2"],
        },
    )


def _build_mixed_profile() -> CandidateProfile:
    return CandidateProfile(
        canonical_profile={
            "target_role": "Senior Product Analyst",
            "experience_years": 4,
            "jobs": [
                {
                    "id": 1,
                    "company_name": "GrowthLoop",
                    "position": "Senior Product Analyst",
                    "period": "2022 - Present",
                    "responsibilities": [
                        "Built product dashboards in Looker and SQL.",
                        "Increased retention by 12% through cohort analysis and experiment design.",
                        "Worked with Python and Amplitude.",
                    ],
                    "achievements": [],
                    "skills_used": [],
                }
            ],
            "skills_hard": ["SQL", "Python", "Looker", "Amplitude", "Experiment design"],
            "education": [
                {"institution": "Higher School of Economics", "degree": "Bachelor", "field": "Applied Mathematics", "year": "2022"}
            ],
            "languages": [{"name": "English"}, {"name": "German"}],
        },
        evidence={
            "target_role": ["Senior Product Analyst"],
            "experience_years": ["Total experience: 4 years 3 months"],
            "job_1_company": ["GrowthLoop SaaS platform"],
            "job_1_position": ["Senior Product Analyst"],
            "job_1_period": ["2022 - Present"],
            "job_1_responsibilities": ["Built product dashboards in Looker and SQL."],
            "job_1_achievements": ["Increased retention by 12% through cohort analysis and experiment design."],
            "job_1_skills_used": ["Worked with Python and Amplitude."],
            "skills_hard": ["SQL, Python, Looker, Amplitude, Experiment design"],
            "education": ["Bachelor, Applied Mathematics"],
            "languages": ["English — Upper-Intermediate", "German (basic)"],
        },
    )


def _build_short_profile() -> CandidateProfile:
    return CandidateProfile(
        canonical_profile={
            "target_role": "Data Analyst",
            "experience_years": 1,
            "jobs": [
                {
                    "id": 1,
                    "company_name": "Acme Marketing Agency",
                    "position": "Data Analyst",
                    "period": "2023 - 2024",
                    "responsibilities": ["Built Tableau dashboard for campaign reporting."],
                    "achievements": [],
                    "skills_used": [],
                }
            ],
            "skills_hard": ["SQL", "Tableau"],
            "languages": [LanguageItem(name="English", level=None)],
        },
        evidence={
            "target_role": ["Data Analyst"],
            "experience_years": ["Experience: 1 year 6 months"],
            "job_1_company": ["Acme Marketing Agency"],
            "job_1_position": ["Data Analyst"],
            "job_1_period": ["2023 - 2024"],
            "job_1_responsibilities": ["Built Tableau dashboard for campaign reporting."],
            "job_1_skills_used": ["Built Tableau dashboard for campaign reporting."],
            "skills_hard": ["SQL, Tableau"],
            "languages": ["English"],
        },
    )


def main() -> int:
    preview = detect_resume_sections(HH_RU_RESUME, soft_input_budget=2500)
    assert "work_experience" in preview.section_preview
    assert "skills" in preview.section_preview

    hh_profile = normalize_candidate_profile(_build_hh_like_profile(), HH_RU_RESUME)
    assert hh_profile.experience_years == 2
    assert hh_profile.experience_months == 32
    assert hh_profile.jobs[0].company_type == "bank / financial sector"
    assert hh_profile.jobs[0].achievements == ["Увеличил точность риск-мониторинга на 18%"]
    assert "Power BI" in hh_profile.jobs[0].skills_used
    assert hh_profile.canonical_profile.languages[0].level == "Native"
    assert hh_profile.canonical_profile.languages[1].level == "B2"
    assert any("2 года 8 месяцев" in snippet for snippet in hh_profile.evidence.total_experience)
    assert len(hh_profile.evidence.jobs) == len(hh_profile.jobs)
    assert hh_profile.provenance["job_1_period"][0].source_block_id == "job_source:1"
    assert CANDIDATE_EVIDENCE_VALIDATION_ENABLED is False
    assert hh_profile.provenance["job_1_period"][0].extraction_mode == "llm_unvalidated"
    assert hh_profile.provenance["job_1_period"][0].validation_status == "not_validated"
    assert hh_profile.provenance["job_2_period"][0].source_block_id == "job_source:2"
    assert hh_profile.provenance["job_2_period"][0].extraction_mode == "llm_unvalidated"
    assert "Февраль 2024" not in " ".join(hh_profile.evidence.jobs[0].period)
    assert "Октябрь 2024 — настоящее время" not in " ".join(hh_profile.evidence.jobs[1].period)

    mixed_profile = normalize_candidate_profile(_build_mixed_profile(), MIXED_RESUME)
    assert mixed_profile.experience_months == 51
    assert mixed_profile.jobs[0].company_type == "software / SaaS"
    assert mixed_profile.jobs[0].achievements == ["Increased retention by 12% through cohort analysis and experiment design"]
    assert "Looker" in mixed_profile.jobs[0].skills_used
    assert mixed_profile.canonical_profile.languages[0].level == "Upper-Intermediate"
    assert mixed_profile.canonical_profile.languages[1].level == "Basic"
    assert mixed_profile.provenance["job_1_highlights"][0].source_block_id == "job_source:1"
    assert mixed_profile.provenance["job_1_highlights"][0].extraction_mode == "llm_unvalidated"
    assert mixed_profile.evidence.languages == ["English — Upper-Intermediate", "German (basic)"]

    short_profile = normalize_candidate_profile(_build_short_profile(), SHORT_RESUME)
    assert short_profile.experience_months == 18
    assert short_profile.jobs[0].company_type == "marketing agency"
    assert short_profile.confidence.languages in {"low", "medium"}
    assert short_profile.canonical_profile.languages[0].level is None
    assert short_profile.provenance["job_1_company"][0].source_block_id == "job_source:1"
    assert short_profile.provenance["job_1_company"][0].extraction_mode == "llm_unvalidated"
    assert short_profile.provenance["education"][0].extraction_mode == "missing"

    section_response = """[TARGET_ROLE]
Аналитик данных

[EXPERIENCE_MONTHS]
32

[EXPERIENCE_RAW]
Опыт работы — 2 года 8 месяцев

[SUMMARY_RAW]

[JOB_1]
company: Совкомбанк Лизинг — банк, финансовый сектор
company_type: Banking
position: Риск аналитик
period: Октябрь 2024 — настоящее время
highlights:
- Настроил систему мониторинга кредитного риска: дашборды в Tableau/Power BI.
- Автоматизировал отчётность в SQL и Python.

[SKILLS_HARD]
SQL; Python; Power BI; Tableau

[SKILLS_SOFT]

[EDUCATION]
1 | НИУ ВШЭ | Бакалавр | Прикладная математика и информатика | 2025 | completed

[LANGUAGES]
Русский | Native
Английский | B2

[CERTIFICATIONS]

[AMBIGUITIES]
- Target role extracted from desired role section

[WARNINGS]
"""

    provider = FakeProvider([section_response])
    parsed = provider.parse_candidate_profile(HH_RU_RESUME)

    assert len(provider.calls) == 1
    assert provider.calls[0]["model"] == OPENAI_MODEL
    assert provider.calls[0]["temperature"] == 0.1
    assert provider.calls[0]["max_output_tokens"] == 1200
    assert parsed.experience_months == 32
    assert parsed.jobs[0].company_type == "bank / financial sector"
    assert parsed.evidence.jobs[0].company == ["Совкомбанк Лизинг — банк, финансовый сектор"]
    assert parsed.provenance["job_1_company"][0].source_block_id == "job_source:1"

    follow_ups = build_follow_up_questions(parsed)
    assert len(follow_ups) <= 3

    print("candidate profile stage checks passed")
    print(json.dumps({
        "hh_like": hh_profile.model_dump(),
        "mixed_ru_en": mixed_profile.model_dump(),
        "short_semi_structured": short_profile.model_dump(),
        "follow_up_questions": follow_ups,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
