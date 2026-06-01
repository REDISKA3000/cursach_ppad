from __future__ import annotations

import logging
from functools import lru_cache

from app.data.role_profiles import ROLE_PROFILE_ALIASES, ROLE_PROFILE_PRESETS
from app.schemas.role_relevance import RoleProfile

logger = logging.getLogger(__name__)


def _normalize_role_key(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def generate_role_profile_with_llm(target_role: str) -> RoleProfile | None:
    """Reserved extension point for LLM role-profile generation.

    The local MVP deliberately returns None unless a real provider is wired in,
    so the project stays runnable without an API key.
    """
    return None


def _build_generic_profile(target_role: str) -> RoleProfile:
    role = target_role.strip() or "Unknown role"
    return RoleProfile(
        target_role=role,
        canonical_role=role,
        role_family=role,
        role_type="individual_contributor",
        synonyms=[role],
        must_have_concepts=[role],
        related_concepts=[],
        negative_concepts=[],
        adjacent_roles=[],
        excluded_roles=[],
    )


@lru_cache(maxsize=128)
def build_role_profile(target_role: str, use_llm: bool = False) -> RoleProfile:
    key = _normalize_role_key(target_role)
    preset_key = ROLE_PROFILE_ALIASES.get(key, key)
    preset = ROLE_PROFILE_PRESETS.get(preset_key)
    if preset:
        profile = RoleProfile(**{**preset, "target_role": target_role.strip() or preset["target_role"]})
        logger.info("[RoleProfile] created preset profile for target_role=%s", target_role)
        return profile

    if use_llm:
        generated = generate_role_profile_with_llm(target_role)
        if generated:
            logger.info("[RoleProfile] created LLM profile for target_role=%s", target_role)
            return generated

    logger.warning("[RoleProfile] no preset for target_role=%s, using generic fallback", target_role)
    return _build_generic_profile(target_role)
