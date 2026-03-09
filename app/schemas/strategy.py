from pydantic import BaseModel
from typing import Optional, List

class StrategyBrief(BaseModel):
    positioning: str = ""
    fit_score: float = 0.0
    highlight_job_ids: List[int] = []
    downplay_job_ids: List[int] = []
    skills_to_highlight: List[str] = []
    skills_to_soften: List[str] = []
    gaps: List[str] = []
    resume_variants: List[str] = []
    recommendations_short: str = ""
