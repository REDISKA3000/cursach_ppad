from pydantic import BaseModel
from typing import List, Literal, Optional

class StrategyBrief(BaseModel):
    positioning: str = ""
    fit_score: float = 0.0
    qualitative_fit: str = ""
    support_fit_score: Optional[float] = None
    highlight_job_ids: List[int] = []
    downplay_job_ids: List[int] = []
    skills_to_highlight: List[str] = []
    skills_to_soften: List[str] = []
    achievement_highlights: List[str] = []
    priority_themes: List[str] = []
    gaps: List[str] = []
    resume_variants: List[str] = []
    recommendations_short: str = ""
    strategy_confidence: Literal["low", "medium", "high"] = "medium"
    fallback_used: bool = False
    strategy_warnings: List[str] = []
