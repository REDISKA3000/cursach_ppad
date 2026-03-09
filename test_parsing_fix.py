#!/usr/bin/env python3
"""Test the fixed parsing pipeline with sample data"""

import sys
sys.path.insert(0, '/Users/egorgladilin/vscodeProjects/curshad_ppad')

from app.services.mock_llm import MockLLM
from app.agents.candidate_profile_agent import CandidateProfileAgent
from app.agents.vacancy_analyzer_agent import VacancyAnalyzerAgent
from app.agents.career_strategy_agent import CareerStrategyAgent
from app.agents.resume_writer_critic_agent import ResumeWriterCriticAgent
from app.services.orchestration import OrchestrationService

# Sample resume data for Ivan Petrov (Product Manager)
SAMPLE_RESUME = """
ИВАН ПЕТРОВ
Email: ivan.petrov@example.com
Tel: +7-999-123-4567

Опыт: 5 лет продуктовой разработке

ПРОФЕССИОНАЛЬНАЯ ЦЕЛЬ: Старший Product Manager в финтехе

КЛЮЧЕВЫЕ НАВЫКИ:
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
- Работал с design, tech и data teams для экспорта feature

Ozon
Product Manager
2019 - 2021

- Отвечал за категорию электроники и товаров для дома
- Провел исследование потребителей, выявил top-3 боли (доставка, цена, отзывы)
- Разработал KPI для категории: упор на retention через персонализацию
- Запустил персонализированные рекомендации, увеличил AOV на 18%
- Анализировал конкурентов и тренды рынка е-commerce
- Координировал работу с логистикой и маркетингом

ОБРАЗОВАНИЕ:
Московский государственный университет
Магистратура: Экономика, 2019

ЯЗЫКИ:
Русский (родной), Английский (B1)
"""

# Sample vacancy for FinTech PM role
SAMPLE_VACANCY = """
ВАКАНСИЯ: Senior Product Manager (FinTech)

Компания: StartupBank

ТРЕБУЕМЫЕ НАВЫКИ (MUST-HAVE):
- Product Strategy
- A/B-тесты
- SQL
- Продуктовая аналитика
- Работа с данными
- Управление roadmap

NICE-TO-HAVE:
- Финтех опыт
- Опыт с микросервисной архитектурой
- ML basics
- People management

ОПИСАНИЕ:
Нужен опытный Product Manager для развития платежной платформы. 
Основной фокус - увеличение конверсии и retention.
"""

def main():
    print("=" * 80)
    print("TESTING PARSE CANDIDATE PROFILE FIX")
    print("=" * 80)
    print()
    
    # Step 1: Test Mock LLM parsing
    print("STEP 1: Testing MockLLM parse_candidate_profile")
    print("-" * 80)
    mock_llm = MockLLM()
    
    candidate = mock_llm.parse_candidate_profile(SAMPLE_RESUME)
    
    print(f"\n✓ Target role: {candidate.target_role}")
    print(f"✓ Experience years: {candidate.experience_years}")
    
    # Verify experience years fix
    expected_years = 5
    if candidate.experience_years == expected_years:
        print(f"  ✅ PASS: Experience years correct (expected {expected_years}, got {candidate.experience_years})")
    else:
        print(f"  ❌ FAIL: Experience years wrong (expected {expected_years}, got {candidate.experience_years})")
    
    # Verify skills preserved
    print(f"\n✓ Hard skills count: {len(candidate.skills_hard)}")
    expected_skills = {"SQL", "A/B-тесты", "Продуктовая аналитика", "Юнит-экономика", 
                      "CJM", "Growth", "Retention", "Product Strategy", "Backlog management"}
    actual_skills = set(candidate.skills_hard)
    
    for skill in expected_skills:
        if any(skill.lower() in s.lower() for s in candidate.skills_hard):
            print(f"  ✅ Found: {skill}")
        else:
            print(f"  ❌ Missing: {skill}")
    
    # Verify jobs parsed correctly
    print(f"\n✓ Jobs count: {len(candidate.jobs)}")
    expected_job_count = 2
    if len(candidate.jobs) == expected_job_count:
        print(f"  ✅ PASS: Job count correct (expected {expected_job_count}, got {len(candidate.jobs)})")
    else:
        print(f"  ❌ FAIL: Job count wrong (expected {expected_job_count}, got {len(candidate.jobs)})")
    
    # Check each job
    for i, job in enumerate(candidate.jobs):
        print(f"\n  Job {i+1}:")
        print(f"    Company: {job.company_name}")
        print(f"    Position: {job.position}")
        print(f"    Period: {job.period}")
        print(f"    Responsibilities: {len(job.responsibilities)} items")
        
        # Check for generic placeholders
        has_generic = False
        for resp in job.responsibilities:
            if any(x in resp.lower() for x in ["contributed to team", "participated in", "helped improve"]):
                has_generic = True
                print(f"      ⚠️  Generic: {resp}")
        
        if not has_generic:
            print(f"      ✅ No generic placeholders found")
        
        # Show sample responsibilities
        for resp in job.responsibilities[:2]:
            print(f"      • {resp}")
    
    # Verify education
    print(f"\n✓ Education: {len(candidate.education)} entries")
    if candidate.education:
        for edu in candidate.education:
            print(f"  - {edu.institution}")
    
    # Verify languages
    print(f"\n✓ Languages: {', '.join(candidate.languages)}")
    
    print("\n" + "=" * 80)
    print("STEP 2: Testing full orchestration pipeline")
    print("-" * 80)
    
    # Test full pipeline
    orch = OrchestrationService()
    
    print("\n1. Processing resume...")
    processed_candidate = orch.process_resume(SAMPLE_RESUME)
    print(f"   ✓ Candidate processed: {processed_candidate.target_role}, {processed_candidate.experience_years} years")
    
    print("\n2. Processing vacancy...")
    vacancy = orch.process_vacancy(SAMPLE_VACANCY)
    print(f"   ✓ Vacancy processed: {vacancy.role}, {len(vacancy.must_have_skills)} must-haves")
    
    print("\n3. Building strategy...")
    strategy = orch.build_strategy(processed_candidate, vacancy)
    print(f"   ✓ Strategy built: {len(strategy.skills_to_highlight)} skills highlighted")
    print(f"     Positioning: {strategy.positioning}")
    
    print("\n4. Generating resume...")
    generated = orch.generate_resume(processed_candidate, vacancy, strategy)
    print(f"   ✓ Resume generated: {generated.title}")
    
    # Check for generic placeholders in final resume
    generic_phrases = ["contributed to team", "participated in", "helped improve", "worked on various", "various responsibilities"]
    has_generic = any(phrase in generated.resume_text.lower() for phrase in generic_phrases)
    
    if has_generic:
        print(f"   ❌ WARNING: Generic placeholders found in resume")
    else:
        print(f"   ✅ No generic placeholders in final resume")
    
    # Print warnings from critic
    print(f"\n5. Technical Report:")
    print(f"   Covered must-haves: {generated.technical_report.covered_must_haves}")
    print(f"   Uncovered must-haves: {generated.technical_report.uncovered_must_haves}")
    print(f"   Critic warnings: {generated.technical_report.critic_warnings}")
    
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    # Summary checks
    checks = {
        "Experience years = 5": candidate.experience_years == 5,
        "All skills preserved": len(actual_skills.intersection(expected_skills)) >= 5,
        "Exactly 2 jobs": len(candidate.jobs) == 2,
        "No generic placeholders": not has_generic,
        "Education found": len(candidate.education) > 0,
        "Languages found": len(candidate.languages) > 0,
    }
    
    for check, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {check}")
    
    all_pass = all(checks.values())
    print()
    if all_pass:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ Some tests failed - see details above")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
