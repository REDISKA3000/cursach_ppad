"""Resume Writer & Critic Agent"""
import logging
from app.schemas.candidate import CandidateProfile
from app.schemas.vacancy import VacancyProfile
from app.schemas.strategy import StrategyBrief
from app.schemas.resume import GeneratedResume
from app.services.llm_provider import get_llm_provider
from app.services.resume_writer_stage import build_deterministic_resume

logger = logging.getLogger(__name__)

class ResumeWriterCriticAgent:
    def __init__(self):
        self.llm = get_llm_provider()
    
    def generate_resume(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        strategy_brief: StrategyBrief
    ) -> GeneratedResume:
        """
        Generate adapted resume based on strategy
        
        Inputs:
        - candidate_profile: Candidate's data
        - vacancy_profile: Job requirements
        - strategy_brief: Strategic recommendations
        
        Output: GeneratedResume with text and technical report
        """
        try:
            return self.llm.generate_resume(candidate_profile, vacancy_profile, strategy_brief)
        except Exception as e:
            logger.error(f"Error generating resume: {e}")
            return build_deterministic_resume(
                candidate_profile,
                vacancy_profile,
                strategy_brief,
                reason=str(e),
            )
