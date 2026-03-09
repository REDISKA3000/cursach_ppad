"""Resume Writer & Critic Agent"""
import logging
from app.schemas.candidate import CandidateProfile
from app.schemas.vacancy import VacancyProfile
from app.schemas.strategy import StrategyBrief
from app.schemas.resume import TechnicalReport, GeneratedResume
from app.services.llm_provider import get_llm_provider

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
            # Build structured resume text
            resume_text = self._build_resume_from_profile(
                candidate_profile,
                vacancy_profile,
                strategy_brief
            )
            
            # Generate technical report
            report = self._generate_technical_report(
                candidate_profile,
                vacancy_profile,
                strategy_brief,
                resume_text
            )
            
            generated_resume = GeneratedResume(
                title=f"Резюме для {vacancy_profile.role or 'должности'}",
                resume_text=resume_text,
                technical_report=report
            )
            
            return generated_resume
        except Exception as e:
            logger.error(f"Error generating resume: {e}")
            return GeneratedResume(
                title="Ошибка при генерации резюме",
                resume_text="Произошла ошибка при генерации резюме",
                technical_report=TechnicalReport(
                    critic_warnings=["Error in resume generation"]
                )
            )
    
    def _build_resume_from_profile(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        strategy_brief: StrategyBrief
    ) -> str:
        """Build resume text from actual profile data only"""
        
        parts = []
        
        # Header
        parts.append("=" * 70)
        parts.append(f"ПРОФЕССИОНАЛЬНОЕ РЕЗЮМЕ")
        parts.append("=" * 70)
        parts.append("")
        
        # Professional Summary
        parts.append("ПРОФЕССИОНАЛЬНАЯ СВОДКА")
        if candidate_profile.target_role:
            parts.append(f"Позиция: {candidate_profile.target_role}")
        if candidate_profile.experience_years:
            parts.append(f"Опыт: {candidate_profile.experience_years} лет")
        if strategy_brief.positioning:
            parts.append(f"Позиционирование: {strategy_brief.positioning}")
        parts.append("")
        
        # Key Skills - USE ACTUAL SKILLS ONLY
        if candidate_profile.skills_hard:
            parts.append("КЛЮЧЕВЫЕ НАВЫКИ")
            skills_to_highlight = strategy_brief.skills_to_highlight or candidate_profile.skills_hard[:5]
            parts.append(", ".join(skills_to_highlight))
            parts.append("")
        
        # Work Experience - USE REAL RESPONSIBILITIES ONLY
        if candidate_profile.jobs:
            parts.append("ОПЫТ РАБОТЫ")
            for job in candidate_profile.jobs:
                if strategy_brief.highlight_job_ids and job.id not in strategy_brief.highlight_job_ids:
                    continue  # Skip non-highlighted jobs in strict mode
                
                parts.append("")
                
                # Position and company
                if job.position and job.company_name:
                    parts.append(f"{job.position}")
                    parts.append(f"Компания: {job.company_name}")
                elif job.position:
                    parts.append(f"{job.position}")
                
                # Period
                if job.period:
                    parts.append(f"Период: {job.period}")
                
                # Responsibilities - ONLY REAL ONES FROM PROFILE
                if job.responsibilities:
                    for resp in job.responsibilities[:5]:  # Max 5 per job
                        # Only include if it's not generic placeholder
                        if not self._is_generic_placeholder(resp):
                            parts.append(f"• {resp}")
                
                # Achievements - ONLY IF REAL
                if job.achievements:
                    for ach in job.achievements[:3]:
                        if not self._is_generic_placeholder(ach):
                            parts.append(f"✓ {ach}")
        
        parts.append("")
        
        # Education
        if candidate_profile.education:
            parts.append("ОБРАЗОВАНИЕ")
            for edu in candidate_profile.education:
                if edu.institution:
                    parts.append(edu.institution)
                if edu.degree:
                    parts.append(f"Степень: {edu.degree}")
                if edu.year:
                    parts.append(f"Год: {edu.year}")
                parts.append("")
        
        # Languages
        if candidate_profile.languages:
            parts.append("ЯЗЫКИ")
            parts.append(", ".join(candidate_profile.languages))
            parts.append("")
        
        # Skills soft
        if candidate_profile.skills_soft:
            parts.append("ЛИЧНЫЕ КАЧЕСТВА")
            parts.append(", ".join(candidate_profile.skills_soft))
        
        return "\n".join(parts)
    
    def _is_generic_placeholder(self, text: str) -> bool:
        """Check if text is a generic placeholder that should never appear"""
        generic_phrases = [
            "contributed to team",
            "improved performance",
            "participated in",
            "worked on various",
            "gained experience",
            "collaborated across",
            "involved in projects",
            "various responsibilities",
            "key responsibilities",
            "worked on projects",
            "contributed to team projects",
            "helped improve",
            "assisted in",
        ]
        
        text_lower = text.lower()
        for phrase in generic_phrases:
            if phrase in text_lower:
                return True
        
        return False
    
    def _generate_technical_report(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        strategy_brief: StrategyBrief,
        resume_text: str
    ) -> TechnicalReport:
        """Generate technical report with validation"""
        
        report = TechnicalReport()
        
        # Highlighted jobs
        report.highlighted_jobs = strategy_brief.highlight_job_ids
        
        # Highlighted skills
        report.highlighted_skills = strategy_brief.skills_to_highlight
        
        # Covered must-haves with synonym normalization and fuzzy matching
        candidate_skills_lower = set(s.lower() for s in candidate_profile.skills_hard)
        must_haves = vacancy_profile.must_have_skills

        # Simple synonym map (extendable)
        synonym_map = {
            "product manager": ["pm", "product manager", "продукт менеджер", "product owner"],
            "fintech": ["fintech", "финтех"],
            "a/b testing": ["a/b-testing", "a/b тесты", "a/b тестирование", "ab test"],
        }

        def normalize(skill: str) -> str:
            s = skill.lower().strip()
            for key, aliases in synonym_map.items():
                if s in aliases or any(alias in s for alias in aliases):
                    return key
            return s

        normalized_candidate = set(normalize(s) for s in candidate_skills_lower)
        normalized_must = set(normalize(s) for s in must_haves)

        covered = normalized_must & normalized_candidate
        uncovered = normalized_must - normalized_candidate

        report.covered_must_haves = list(covered)
        report.uncovered_must_haves = list(uncovered)
        
        # Critic warnings
        warnings = []
        
        # Check for generic placeholders in resume
        if any(self._is_generic_placeholder(line) for line in resume_text.split('\n')):
            warnings.append("⚠️ Обнаружены шаблонные фразы - требуется редоработка")
        
        # Check if covered must-haves are properly reflected
        if not report.covered_must_haves and must_haves_lower:
            warnings.append("⚠️ Требуемые навыки недостаточно отражены в резюме")
        
        # Check for too many gaps
        if len(report.uncovered_must_haves) > len(report.covered_must_haves):
            warnings.append("⚠️ Больше недостаточных требований, чем покрытых - кандидат слабо подходит")
        
        # Check if all jobs have real responsibilities
        for job in candidate_profile.jobs:
            if not job.responsibilities or all(self._is_generic_placeholder(r) for r in job.responsibilities):
                warnings.append(f"⚠️ Место работы '{job.position}' не имеет реальной информации")
        
        report.critic_warnings = warnings
        
        return report

