#!/usr/bin/env python3
"""Test fixed parsing pipeline"""

import sys
sys.path.insert(0, '/Users/egorgladilin/vscodeProjects/curshad_ppad')

from app.services.mock_llm import MockLLM

SAMPLE_RESUME = """
ИВАН ПЕТРОВ
Email: ivan.petrov@example.com
Tel: +7-999-123-4567

Опыт: 5 лет

ПРОФЕССИОНАЛЬНАЯ ЦЕЛЬ: Старший Product Manager в финтехе

НАВЫКИ:
Product Strategy, Product Roadmap, A/B-тесты, SQL, Продуктовая аналитика, 
Юнит-экономика, CJM, Backlog management, Growth, Retention

ОПЫТ РАБОТЫ:

Т-Банк (TCS Bank)
Senior Product Manager / Head of Product
2021 - 2024

- Управлял портфелем платежных продуктов для мобильного приложения
- Провел A/B-тесты новых юзер-флоу, улучшился CTR на 23%
- Запустил feature управления финансовыми целями, ROI +15%
- Построил процесс сбора requirements от sales/support команд
- Определил метрики успеха продукта (DAU, retention, LTV)
- Работал с design, tech и data teams

Ozon
Product Manager
2019 - 2021

- Отвечал за категорию электроники и товаров для дома
- Провел исследование потребителей, выявил top-3 боли (доставка, цена, отзывы)
- Разработал KPI для категории: упор на retention
- Запустил персонализированные рекомендации, увеличил AOV на 18%
- Анализировал конкурентов и тренды рынка
- Координировал работу с логистикой и маркетингом

ОБРАЗОВАНИЕ:
НИУ ВШЭ, Бакалавриат, Менеджмент, 2019

ЯЗЫКИ:
Русский (родной), Английский (B1)
"""

SAMPLE_VACANCY = """
ВАКАНСИЯ: Senior Product Manager (FinTech)

Компания: StartupBank

ТРЕБОВАНИЯ:
- SQL
- A/B-тестирование
- Продуктовая аналитика
- Юнит-экономика
- Опыт в FinTech
- Опыт Product Manager от 3+ лет

БУДЕТ ПЛЮСОМ:
- People Management
- ML Basics

ЗАДАЧИ:
- Увеличение конверсии и retention
- Разработка дорожной карты продукта
"""

def main():
    print("=" * 80)
    print("COMPREHENSIVE PARSING FIX TEST")
    print("=" * 80)
    print()
    
    mock_llm = MockLLM()
    
    # STEP 1: Test Candidate Profile Parsing
    print("STEP 1: Candidate Profile Parsing")
    print("-" * 80)
    candidate = mock_llm.parse_candidate_profile(SAMPLE_RESUME)
    
    print(f"\n✓ Target Role: {candidate.target_role}")
    print(f"✓ Experience: {candidate.experience_years} years")
    print(f"✓ Hard Skills ({len(candidate.skills_hard)}): {candidate.skills_hard}")
    print(f"✓ Soft Skills: {candidate.skills_soft}")
    print(f"✓ Jobs ({len(candidate.jobs)}):")
    for i, job in enumerate(candidate.jobs, 1):
        print(f"  {i}. {job.position} @ {job.company_name} ({job.period})")
        print(f"     Responsibilities: {len(job.responsibilities)}")
        print(f"     Achievements: {len(job.achievements)}")
    
    print(f"\n✓ Education ({len(candidate.education)}):")
    for edu in candidate.education:
        print(f"  - {edu.institution}, {edu.degree}, {edu.year}")
    
    print(f"\n✓ Languages: {candidate.languages}")
    
    # STEP 2: Test Vacancy Profile Parsing
    print("\n" + "=" * 80)
    print("STEP 2: Vacancy Profile Parsing")
    print("-" * 80)
    vacancy = mock_llm.parse_vacancy_profile(SAMPLE_VACANCY)
    
    print(f"\n✓ Role: {vacancy.role}")
    print(f"✓ Seniority: {vacancy.seniority}")
    print(f"✓ Industry: {vacancy.industry}")
    print(f"\n✓ Must-Have Skills ({len(vacancy.must_have_skills)}):")
    for skill in vacancy.must_have_skills:
        print(f"  - {skill}")
    
    print(f"\n✓ Nice-to-Have Skills ({len(vacancy.nice_to_have_skills)}):")
    for skill in vacancy.nice_to_have_skills:
        print(f"  - {skill}")
    
    print(f"\n✓ Key Responsibilities ({len(vacancy.key_responsibilities)}):")
    for resp in vacancy.key_responsibilities:
        print(f"  - {resp}")
    
    # STEP 3: Test Strategy Building
    print("\n" + "=" * 80)
    print("STEP 3: Strategy Building")
    print("-" * 80)
    strategy = mock_llm.build_strategy(candidate, vacancy)
    
    print(f"\n✓ Positioning: {strategy.positioning}")
    print(f"✓ Fit Score: {strategy.fit_score:.2f}")
    print(f"✓ Skills to Highlight: {strategy.skills_to_highlight}")
    print(f"✓ Gaps: {strategy.gaps}")
    
    # STEP 4: Test Resume Generation
    print("\n" + "=" * 80)
    print("STEP 4: Resume Generation")
    print("-" * 80)
    resume = mock_llm.generate_resume(candidate, vacancy, strategy)
    
    print(f"\n✓ Title: {resume.title}")
    print(f"✓ Resume Length: {len(resume.resume_text)} chars")
    print(f"\n✓ Technical Report:")
    print(f"  - Covered Must-Haves: {resume.technical_report.covered_must_haves}")
    print(f"  - Uncovered Must-Haves: {resume.technical_report.uncovered_must_haves}")
    
    # STEP 5: Validation Checks
    print("\n" + "=" * 80)
    print("VALIDATION CHECKS")
    print("-" * 80)
    
    checks = {
        "✓ Education parsing fixed (only 1 valid entry)": len(candidate.education) == 1,
        "✓ No skills duplicates (hard)": len(candidate.skills_hard) == len(set(s.lower() for s in candidate.skills_hard)),
        "✓ No soft skills garbage": 'аналит' not in [s.lower() for s in candidate.skills_soft],
        "✓ Exactly 2 jobs": len(candidate.jobs) == 2,
        "✓ Vacancy role extracted": vacancy.role and 'product manager' in vacancy.role.lower(),
        "✓ Vacancy industry FinTech": vacancy.industry == 'FinTech',
        "✓ Must-have skills populated": len(vacancy.must_have_skills) > 0,
        "✓ Nice-to-have skills populated": len(vacancy.nice_to_have_skills) > 0,
        "✓ Key responsibilities from section": len(vacancy.key_responsibilities) > 0,
        "✓ Strategy positioning good": len(strategy.positioning) > 10,
        "✓ Covered must-haves > 0": len(resume.technical_report.covered_must_haves) > 0,
        "✓ Resume has education": 'ОБРАЗОВАНИЕ' in resume.resume_text,
    }
    
    passed = 0
    for check, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {check}")
        if result:
            passed += 1
    
    print(f"\n{passed}/{len(checks)} CHECKS PASSED")
    
    # STEP 6: Show Resume Preview
    print("\n" + "=" * 80)
    print("RESUME PREVIEW (first 1000 chars)")
    print("-" * 80)
    print(resume.resume_text[:1000])
    print("...\n")
    
    return 0 if passed == len(checks) else 1

if __name__ == "__main__":
    sys.exit(main())
