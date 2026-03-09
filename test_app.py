#!/usr/bin/env python3
"""
Quick test to verify the application works
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("Testing Resume Career Consultant MVP")
print("=" * 60)

# Test 1: Import modules
print("\n✓ Test 1: Importing modules...")
try:
    from app.db import init_db
    from app.models import User, Conversation, Message, ResumeGeneration
    from app.schemas.candidate import CandidateProfile
    from app.schemas.vacancy import VacancyProfile
    from app.schemas.strategy import StrategyBrief
    from app.services.mock_llm import MockLLM
    from app.services.orchestration import OrchestrationService
    print("  ✅ All modules imported successfully")
except Exception as e:
    print(f"  ❌ Import error: {e}")
    sys.exit(1)

# Test 2: Initialize database
print("\n✓ Test 2: Initializing database...")
try:
    init_db()
    print("  ✅ Database initialized")
except Exception as e:
    print(f"  ❌ Database error: {e}")
    sys.exit(1)

# Test 3: Test Mock LLM
print("\n✓ Test 3: Testing Mock LLM...")
try:
    llm = MockLLM()
    
    sample_resume = """
    John Smith
    Senior Developer
    
    Experience:
    - Python, JavaScript, SQL
    - 5 years in tech
    
    Education:
    University of Technology, BS Computer Science
    """
    
    profile = llm.parse_candidate_profile(sample_resume)
    print(f"  ✅ Mock LLM works: {len(profile.jobs)} jobs, {len(profile.skills_hard)} skills")
except Exception as e:
    print(f"  ❌ Mock LLM error: {e}")
    sys.exit(1)

# Test 4: Test Orchestration
print("\n✓ Test 4: Testing Orchestration Service...")
try:
    orchestration = OrchestrationService()
    
    sample_resume = "John Smith\nSenior Developer\n5 years experience\nPython, JavaScript"
    sample_vacancy = "Need Senior Developer with Python skills"
    
    candidate_profile, vacancy_profile, strategy_brief, generated_resume = orchestration.full_flow(
        sample_resume,
        sample_vacancy
    )
    
    print(f"  ✅ Orchestration works:")
    print(f"     - Fit score: {strategy_brief.fit_score}")
    print(f"     - Resume length: {len(generated_resume.resume_text)} chars")
except Exception as e:
    print(f"  ❌ Orchestration error: {e}")
    sys.exit(1)

# Test 5: Test FastAPI app
print("\n✓ Test 5: Testing FastAPI app...")
try:
    from app.main import app
    print("  ✅ FastAPI app loaded successfully")
except Exception as e:
    print(f"  ❌ FastAPI error: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ All tests passed! Application is ready.")
print("=" * 60)
print("\nTo start the server, run:")
print("  python run.py")
print("\nThen visit: http://localhost:8000")
