from pydantic import BaseModel
from typing import List

class TechnicalReport(BaseModel):
    highlighted_jobs: List[int] = []
    highlighted_skills: List[str] = []
    used_highlight_job_ids: List[int] = []
    used_achievement_highlights: List[str] = []
    used_priority_themes: List[str] = []
    covered_must_haves: List[str] = []
    uncovered_must_haves: List[str] = []
    hallucination_checks: List[str] = []
    omitted_strategy_items: List[str] = []
    critic_warnings: List[str] = []
    critic_confidence: str = "medium"
    writer_fallback_used: bool = False
    critic_fallback_used: bool = False
    writer_warnings: List[str] = []

class GeneratedResume(BaseModel):
    title: str
    resume_text: str
    technical_report: TechnicalReport
