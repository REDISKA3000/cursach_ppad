"""Static token-budget and pricing configuration for supported LLM models."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Optional


FLOW_STEPS = [
    "candidate_profile",
    "vacancy_analyzer",
    "career_strategy",
    "resume_writer",
    "resume_critic",
]


MODEL_COSTS: Dict[str, Dict] = {
    "gpt-5.4-mini": {
        "pricing": {
            "input_per_million": 0.75,
            "cached_input_per_million": 0.075,
            "output_per_million": 4.50,
        },
        "token_budgets": {
            "candidate_profile": {"input_tokens": 2000, "output_tokens": 1000},
            "vacancy_analyzer": {"input_tokens": 1200, "output_tokens": 500},
            "career_strategy": {"input_tokens": 800, "output_tokens": 400},
            "resume_writer": {"input_tokens": 1500, "output_tokens": 1500},
            "resume_critic": {"input_tokens": 600, "output_tokens": 300},
        },
    },
    "gpt-5-mini": {
        "pricing": {
            "input_per_million": 0.25,
            "cached_input_per_million": 0.025,
            "output_per_million": 2.00,
        },
        "token_budgets": {
            "candidate_profile": {"input_tokens": 2000, "output_tokens": 2000},
            "vacancy_analyzer": {"input_tokens": 2000, "output_tokens": 2000},
            "career_strategy": {"input_tokens": 2000, "output_tokens": 2000},
            "resume_writer": {"input_tokens": 2000, "output_tokens": 2000},
            "resume_critic": {"input_tokens": 2000, "output_tokens": 2000},
        },
    },
    "gpt-4-turbo": {
        "pricing": {
            "input_per_million": 10.00,
            "output_per_million": 30.00,
        },
        "token_budgets": {
            "candidate_profile": {"input_tokens": 2000, "output_tokens": 2000},
            "vacancy_analyzer": {"input_tokens": 2000, "output_tokens": 2000},
            "career_strategy": {"input_tokens": 2000, "output_tokens": 2000},
            "resume_writer": {"input_tokens": 2000, "output_tokens": 2000},
            "resume_critic": {"input_tokens": 2000, "output_tokens": 2000},
        },
    },
}


def _normalize_model_name(model_name: str) -> str:
    if not model_name:
        return ""
    normalized = model_name.strip()
    for base_name in MODEL_COSTS:
        if normalized == base_name or normalized.startswith(f"{base_name}-"):
            return base_name
    return normalized


def get_model_cost_config(model_name: str) -> Optional[Dict]:
    """Return cost config for a model or snapshot alias."""
    normalized = _normalize_model_name(model_name)
    config = MODEL_COSTS.get(normalized)
    return deepcopy(config) if config else None


def estimate_full_flow_cost(model_name: str) -> Optional[Dict]:
    """Estimate one full pipeline run using static token budgets for the model."""
    config = get_model_cost_config(model_name)
    if not config:
        return None

    pricing = config["pricing"]
    token_budgets = config["token_budgets"]
    step_estimates = []
    total_input = 0
    total_output = 0
    total_cost = 0.0

    for step in FLOW_STEPS:
        budget = token_budgets[step]
        input_tokens = budget["input_tokens"]
        output_tokens = budget["output_tokens"]
        input_cost = input_tokens * pricing["input_per_million"] / 1_000_000
        output_cost = output_tokens * pricing["output_per_million"] / 1_000_000
        step_cost = input_cost + output_cost

        total_input += input_tokens
        total_output += output_tokens
        total_cost += step_cost

        step_estimates.append(
            {
                "step": step,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": round(step_cost, 8),
            }
        )

    return {
        "model": _normalize_model_name(model_name),
        "pricing": pricing,
        "token_budgets": token_budgets,
        "steps": step_estimates,
        "totals": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "estimated_cost_usd": round(total_cost, 8),
        },
    }
