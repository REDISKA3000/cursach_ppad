"""Career Strategy Agent"""
import logging
from typing import Optional, Dict, Any
from app.schemas.candidate import CandidateProfile
from app.schemas.vacancy import VacancyProfile
from app.schemas.strategy import StrategyBrief
from app.services.llm_provider import get_llm_provider
from app.services.career_strategy_stage import build_fallback_strategy

logger = logging.getLogger(__name__)

class CareerStrategyAgent:
    def __init__(self):
        self.llm = get_llm_provider()
    
    def build_strategy(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        candidate_preferences: Optional[Dict[str, Any]] = None
    ) -> StrategyBrief:
        """
        Build strategic brief for resume adaptation
        
        Inputs:
        - candidate_profile: CandidateProfile with candidate data
        - vacancy_profile: VacancyProfile with job requirements
        - candidate_preferences: Optional dict with user preferences
        
        Output: StrategyBrief with positioning, fit_score, and recommendations
        """
        try:
            strategy = self.llm.build_strategy(candidate_profile, vacancy_profile, candidate_preferences)
            self._validate_strategy(strategy, candidate_profile, vacancy_profile)
            return strategy
        except Exception as e:
            logger.error(f"Error building strategy: {e}")
            return self._create_evasive_fallback(candidate_profile, vacancy_profile, str(e))

    def _validate_strategy(
        self,
        strategy: StrategyBrief,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile
    ):
        """Validate strategy and add warnings if needed"""
        
        # Check if fit_score is valid
        if strategy.fit_score < 0 or strategy.fit_score > 1:
            strategy.fit_score = max(0, min(1, strategy.fit_score))
        
        # Check if highlighted jobs actually exist
        valid_job_ids = [job.id for job in candidate_profile.jobs]
        strategy.highlight_job_ids = [jid for jid in strategy.highlight_job_ids if jid in valid_job_ids]
        
        # Ensure we have at least some highlighted jobs
        if not strategy.highlight_job_ids and candidate_profile.jobs:
            strategy.highlight_job_ids = [candidate_profile.jobs[0].id]
    
    def _create_evasive_fallback(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        reason: str = "",
    ) -> StrategyBrief:
        """Create evidence-based fallback even when upstream LLM failed."""
        strategy = build_fallback_strategy(
            candidate_profile,
            vacancy_profile,
            reason=reason or "agent exception",
        )
        self._validate_strategy(strategy, candidate_profile, vacancy_profile)
        return strategy

    def calculate_fit_score(
        self,
        candidate_skills: list,
        must_have_skills: list,
        nice_to_have_skills: list,
        experience_years: Optional[int] = None
    ) -> float:
        """
        Calculate fit score based on skill match
        
        Score components:
        - Must-have coverage: 50%
        - Nice-to-have coverage: 30%
        - Experience level: 20%
        """
        candidate_set = set(skill.lower() for skill in candidate_skills)
        must_have_set = set(skill.lower() for skill in must_have_skills)
        nice_set = set(skill.lower() for skill in nice_to_have_skills)
        
        # Must-have match (50%)
        must_match = 0
        if must_have_set:
            must_match = (len(candidate_set & must_have_set) / len(must_have_set)) * 0.5
        
        # Nice-to-have match (30%)
        nice_match = 0
        if nice_set:
            nice_match = (len(candidate_set & nice_set) / len(nice_set)) * 0.3
        
        # Experience (20%)
        exp_score = 0.0
        if experience_years and experience_years >= 3:
            exp_score = min(0.2, (experience_years / 10) * 0.2)
        elif experience_years and experience_years > 0:
            exp_score = 0.1
        
        total = must_match + nice_match + exp_score
        return min(0.95, total)  # Cap at 95%
    
    def identify_gaps(
        self,
        candidate_skills: list,
        must_have_skills: list
    ) -> list:
        """Identify skill gaps"""
        candidate_set = set(skill.lower() for skill in candidate_skills)
        must_have_set = set(skill.lower() for skill in must_have_skills)
        
        gaps = must_have_set - candidate_set
        return list(gaps)
