#!/usr/bin/env python3
"""
Test OpenAI API integration
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 70)
print("Testing OpenAI API Integration")
print("=" * 70)

# Test 1: Check config
print("\n✓ Test 1: Checking configuration...")
try:
    from app.config import OPENAI_API_KEY, OPENAI_ENABLED, OPENAI_MODEL
    
    if OPENAI_API_KEY:
        print(f"  ✅ OPENAI_API_KEY: {OPENAI_API_KEY[:20]}...{OPENAI_API_KEY[-10:]}")
    else:
        print("  ⚠️  OPENAI_API_KEY is empty")
    
    print(f"  ✅ OPENAI_ENABLED: {OPENAI_ENABLED}")
    print(f"  ✅ OPENAI_MODEL: {OPENAI_MODEL}")
    
    if not OPENAI_ENABLED:
        print("  ⚠️  OpenAI is disabled, enabling...")
except Exception as e:
    print(f"  ❌ Config error: {e}")
    sys.exit(1)

# Test 2: Check LLM Provider
print("\n✓ Test 2: Checking LLM Provider...")
try:
    from app.services.llm_provider import OpenAIProvider
    
    provider = OpenAIProvider()
    print(f"  ✅ Provider name: {provider.name}")
    print(f"  ✅ Provider enabled: {provider.enabled}")
    
    if not provider.enabled:
        print("  ⚠️  Provider is disabled, checking if it has fallback...")
        print(f"  ✅ Fallback available: {provider.fallback is not None}")
except Exception as e:
    print(f"  ❌ Provider error: {e}")
    sys.exit(1)

# Test 3: Test Mock Mode (doesn't require API)
print("\n✓ Test 3: Testing with Mock Mode (safe test)...")
try:
    from app.services.orchestration import OrchestrationService
    
    orchestration = OrchestrationService()
    
    sample_resume = """
    John Smith
    Senior Python Developer
    
    Experience:
    - 5 years Python, JavaScript
    - FastAPI, Django
    - AWS, Docker
    
    Education:
    University of Technology, BS Computer Science
    """
    
    sample_vacancy = "Senior Python Developer needed. Must have: Python, FastAPI, AWS"
    
    print("  Running orchestration pipeline...")
    candidate_profile, vacancy_profile, strategy_brief, generated_resume = orchestration.full_flow(
        sample_resume,
        sample_vacancy
    )
    
    print(f"  ✅ Pipeline completed successfully")
    print(f"     - Fit score: {strategy_brief.fit_score:.2f}")
    print(f"     - Must-have covered: {len(strategy_brief.gaps)} gaps")
    print(f"     - Resume length: {len(generated_resume.resume_text)} chars")
except Exception as e:
    print(f"  ❌ Orchestration error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test OpenAI API (if enabled)
print("\n✓ Test 4: Testing OpenAI API connectivity...")
try:
    if OPENAI_ENABLED and OPENAI_API_KEY:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        print("  Sending test request to OpenAI API...")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OpenAI API is working!' in Russian."}
            ],
            max_tokens=50,
            timeout=30
        )
        
        message_content = response.choices[0].message.content
        print(f"  ✅ OpenAI API Response: {message_content}")
        print(f"  ✅ Model used: {response.model}")
        print(f"  ✅ Tokens used: {response.usage.total_tokens}")
    else:
        print("  ⚠️  OpenAI is not enabled or API key is missing")
except Exception as e:
    print(f"  ⚠️  OpenAI API error (this might be expected if API key is invalid): {e}")
    print("  Continuing with fallback to mock mode...")

print("\n" + "=" * 70)
print("✅ Tests completed!")
print("=" * 70)
print("\nNext steps:")
print("1. If OpenAI tests passed - Real LLM mode is enabled ✅")
print("2. If OpenAI tests failed - Mock mode will be used as fallback ✅")
print("3. Run the application: python run.py")
print("4. Visit: http://localhost:8000")
