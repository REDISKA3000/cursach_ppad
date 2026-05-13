#!/usr/bin/env python3
"""Checks static model token budgets and cost estimates."""

import sys

sys.path.insert(0, "/Users/egorgladilin/vscodeProjects/curshad_ppad")

from app.services.model_costs import estimate_full_flow_cost


def main() -> int:
    estimate = estimate_full_flow_cost("gpt-5.4-mini")
    assert estimate is not None
    assert estimate["totals"]["input_tokens"] == 6_100
    assert estimate["totals"]["output_tokens"] == 3_700
    assert abs(estimate["totals"]["estimated_cost_usd"] - 0.021225) < 1e-9
    assert len(estimate["steps"]) == 5

    mini = estimate_full_flow_cost("gpt-5-mini")
    assert mini is not None
    assert abs(mini["totals"]["estimated_cost_usd"] - 0.0225) < 1e-9

    turbo = estimate_full_flow_cost("gpt-4-turbo")
    assert turbo is not None
    assert abs(turbo["totals"]["estimated_cost_usd"] - 0.4) < 1e-9

    print("model cost checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
