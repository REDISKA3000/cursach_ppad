"""Orchestration service for the complete flow"""
import logging
import json
from typing import Optional, Tuple, Dict, Any
from app.schemas.candidate import CandidateProfile
from app.schemas.vacancy import VacancyProfile
from app.schemas.strategy import StrategyBrief
from app.schemas.resume import GeneratedResume
from app.agents.candidate_profile_agent import CandidateProfileAgent
from app.agents.vacancy_analyzer_agent import VacancyAnalyzerAgent
from app.agents.career_strategy_agent import CareerStrategyAgent
from app.agents.resume_writer_critic_agent import ResumeWriterCriticAgent

logger = logging.getLogger(__name__)

class OrchestrationService:
    """Coordinate all agents in the pipeline"""
    
    def __init__(self):
        self.candidate_agent = CandidateProfileAgent()
        self.vacancy_agent = VacancyAnalyzerAgent()
        self.strategy_agent = CareerStrategyAgent()
        self.resume_agent = ResumeWriterCriticAgent()
    
    def process_resume(self, resume_text: str, candidate_answers: Optional[Dict[str, Any]] = None) -> CandidateProfile:
        """
        Step 1: Process resume and get candidate profile
        """
        profile = self.candidate_agent.parse_resume(resume_text)
        
        if candidate_answers:
            profile = self.candidate_agent.merge_with_answers(profile, candidate_answers)
        
        return profile
    
    def process_vacancy(self, vacancy_text: str) -> VacancyProfile:
        """
        Step 2: Process vacancy and get vacancy profile
        """
        return self.vacancy_agent.parse_vacancy(vacancy_text)
    
    def build_strategy(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        candidate_preferences: Optional[Dict[str, Any]] = None
    ) -> StrategyBrief:
        """
        Step 3: Build strategy based on both profiles
        """
        return self.strategy_agent.build_strategy(candidate_profile, vacancy_profile, candidate_preferences)
    
    def generate_resume(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        strategy_brief: StrategyBrief
    ) -> GeneratedResume:
        """
        Step 4: Generate final resume
        """
        return self.resume_agent.generate_resume(candidate_profile, vacancy_profile, strategy_brief)
    
    def full_flow(
        self,
        resume_text: str,
        vacancy_text: str,
        candidate_answers: Optional[Dict[str, Any]] = None,
        candidate_preferences: Optional[Dict[str, Any]] = None
    ) -> Tuple[CandidateProfile, VacancyProfile, StrategyBrief, GeneratedResume]:
        """
        Run full pipeline from resume to generated resume
        
        Returns: (candidate_profile, vacancy_profile, strategy_brief, generated_resume)
        """
        try:
            # Step 1: Parse resume
            candidate_profile = self.process_resume(resume_text, candidate_answers)
            logger.info(f"Candidate profile parsed: {len(candidate_profile.jobs)} jobs, {len(candidate_profile.skills_hard)} skills")
            
            # Step 2: Parse vacancy
            vacancy_profile = self.process_vacancy(vacancy_text)
            logger.info(f"Vacancy profile parsed: {vacancy_profile.role}, {len(vacancy_profile.must_have_skills)} must-have skills")
            
            # Step 3: Build strategy
            strategy_brief = self.build_strategy(candidate_profile, vacancy_profile, candidate_preferences)
            logger.info(f"Strategy built: fit_score={strategy_brief.fit_score}, gaps={len(strategy_brief.gaps)}")
            
            # Step 4: Generate resume
            generated_resume = self.generate_resume(candidate_profile, vacancy_profile, strategy_brief)
            logger.info(f"Resume generated: {len(generated_resume.resume_text)} chars")
            
            return candidate_profile, vacancy_profile, strategy_brief, generated_resume
        
        except Exception as e:
            logger.error(f"Error in full flow: {e}")
            raise
    
    def get_clarifying_questions(self, candidate_profile: CandidateProfile) -> list:
        """Get questions for the user"""
        return self.candidate_agent.get_clarifying_questions(candidate_profile)
