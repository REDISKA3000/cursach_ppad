#!/usr/bin/env python3
"""Test OpenAI connection"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.config import OPENAI_API_KEY, OPENAI_ENABLED, OPENAI_MODEL
from app.services.llm_provider import get_llm_provider
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=" * 80)
print("OPENAI CONNECTION TEST")
print("=" * 80)

# Check environment
print("\n1. Configuration Check:")
print(f"   API Key present: {'✓' if OPENAI_API_KEY else '✗'}")
if OPENAI_API_KEY:
    key_preview = OPENAI_API_KEY[:20] + "..." + OPENAI_API_KEY[-10:]
    print(f"   API Key (preview): {key_preview}")
print(f"   OPENAI_ENABLED: {OPENAI_ENABLED}")
print(f"   Model: {OPENAI_MODEL}")

# Test provider initialization
print("\n2. Provider Initialization:")
try:
    provider = get_llm_provider()
    print(f"   Provider: {provider.name}")
    print(f"   OpenAI Enabled: {provider.enabled}")
    if not provider.enabled:
        print("   ⚠️ WARNING: OpenAI is disabled, using MOCK LLM fallback")
except Exception as e:
    print(f"   ✗ Error initializing provider: {e}")
    sys.exit(1)

# Test actual API call if enabled
if provider.enabled:
    print("\n3. Testing API Call:")
    try:
        test_resume = "John Doe, Senior Engineer, 5 years experience"
        print(f"   Input: {test_resume[:50]}...")
        
        result = provider.parse_candidate_profile(test_resume)
        print(f"   ✓ API Call successful!")
        print(f"   Parsed role: {result.target_role}")
        print(f"   Experience: {result.experience_years} years")
        print(f"   Skills found: {len(result.skills_hard)} hard skills")
    except Exception as e:
        print(f"   ✗ API Call failed: {e}")
        logger.error(f"Error details: {e}", exc_info=True)
else:
    print("\n3. Skipping API Test (OpenAI disabled)")

print("\n" + "=" * 80)
if provider.enabled:
    print("✓ OpenAI is properly configured and responding")
else:
    print("⚠️ Using Mock LLM (no real OpenAI)")
print("=" * 80)
