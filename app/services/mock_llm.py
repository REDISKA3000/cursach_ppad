"""Mock LLM provider for demo mode"""
import json
import re
from typing import Optional, Dict, Any, List
from app.schemas.candidate import CandidateProfile, CandidateJob, EducationItem
from app.schemas.vacancy import VacancyProfile
from app.schemas.strategy import StrategyBrief
from app.schemas.resume import TechnicalReport, GeneratedResume

class MockLLM:
    """Mock LLM implementation for development and demo"""
    
    def __init__(self):
        self.name = "mock_llm"
    
    def parse_candidate_profile(self, resume_text: str) -> CandidateProfile:
        """Extract candidate profile from resume text using section-based parsing"""
        profile = CandidateProfile()
        
        # Split resume into sections by Russian markers
        sections = self._split_resume_into_sections(resume_text)
        
        # Extract from sections
        profile.experience_years = self._extract_experience_years_v2(sections)
        profile.skills_hard, profile.skills_soft = self._extract_skills_v2(sections)
        profile.jobs = self._extract_jobs_v2(sections)
        profile.education = self._extract_education_v2(sections)
        profile.languages = self._extract_languages_v2(sections)
        profile.target_role = self._extract_target_role_v2(sections)
        
        if not profile.jobs:
            profile.raw_warnings.append("No jobs found in resume")
        
        profile.raw_warnings.append("Profile extracted using section-based parsing")
        return profile
    
    def _split_resume_into_sections(self, text: str) -> Dict[str, str]:
        """Split resume by Russian section markers"""
        sections = {
            'header': '',
            'experience': '',
            'skills': '',
            'education': '',
            'languages': '',
            'other': ''
        }
        
        lines = text.split('\n')
        current_section = 'header'
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip section header lines themselves
            if any(x in line_lower for x in ['опыт работы', 'work experience', 'профессиональный опыт']):
                current_section = 'experience'
                continue
            elif any(x in line_lower for x in ['навыки:', 'skill', 'ключевые навыки', 'компетенции']):
                current_section = 'skills'
                continue
            elif any(x in line_lower for x in ['образование:', 'education', 'учебное']):
                current_section = 'education'
                continue
            elif any(x in line_lower for x in ['язык', 'language', 'иностранные']):
                current_section = 'languages'
                continue
            
            # Accumulate line in current section
            sections[current_section] += line + '\n'
        
        return sections
    
    def _extract_experience_years_v2(self, sections: Dict[str, str]) -> Optional[int]:
        """Extract experience years from header + experience sections"""
        text = sections['header'] + '\n' + sections['experience']
        
        # Pattern 1: "5 лет"
        match = re.search(r'(\d+)\s*(?:лет|год|years?)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Pattern 2: Date ranges "2019-2024"
        matches = re.findall(r'(\d{4})[–\-](\d{4})', text)
        if matches:
            years = [int(m[1]) - int(m[0]) for m in matches]
            return max(years) if years else None
        
        return None
    
    def _extract_skills_v2(self, sections: Dict[str, str]) -> tuple:
        """Extract skills from dedicated section + experience"""
        hard_skills = []
        soft_skills = []
        
        skills_text = sections['skills'] + '\n' + sections['experience']
        text_lower = skills_text.lower()
        
        # Comprehensive keyword matching with case-insensitive deduplication
        tech_keywords = {
            'sql': 'SQL',
            'a/b': 'A/B-тестирование', 'a/b-тест': 'A/B-тестирование', 'ab-test': 'A/B-тестирование',
            'аналитика': 'Продуктовая аналитика', 'аналитик': 'Продуктовая аналитика',
            'юнит-экономика': 'Юнит-экономика', 'юнит экономика': 'Юнит-экономика',
            'метрика': 'Продуктовая аналитика',
            'cjm': 'CJM', 'customer journey': 'CJM',
            'backlog': 'Backlog management', 'бэклог': 'Backlog management',
            'growth': 'Growth', 'грас': 'Growth',
            'retention': 'Retention', 'ретеншн': 'Retention',
            'monetization': 'Монетизация', 'монетизация': 'Монетизация',
            'onboarding': 'Onboarding', 'онбординг': 'Onboarding',
            'product strategy': 'Product Strategy', 'стратегия продукта': 'Product Strategy',
            'product manager': 'Product Manager', 'product owner': 'Product Owner',
            'python': 'Python', 'javascript': 'JavaScript', 'react': 'React',
            'aws': 'AWS', 'docker': 'Docker', 'kubernetes': 'Kubernetes'
        }
        
        # Extract skills with case-insensitive deduplication
        found_skills_lower = set()
        for keyword, skill_name in tech_keywords.items():
            if keyword in text_lower:
                skill_lower = skill_name.lower()
                if skill_lower not in found_skills_lower:
                    hard_skills.append(skill_name)
                    found_skills_lower.add(skill_lower)
        
        # Explicit skills section parsing
        skills_section = sections['skills']
        if skills_section:
            for line in skills_section.split(','):
                skill = line.strip()
                if len(skill) >= 2:
                    skill_lower = skill.lower()
                    if skill_lower not in found_skills_lower:
                        hard_skills.append(skill)
                        found_skills_lower.add(skill_lower)
        
        # Soft skills - also deduplicated
        soft_keywords = {
            'коммуникация': 'Коммуникация',
            'лидерство': 'Лидерство',
            'teamwork': 'Командная работа',
            'аналитическое': 'Аналитическое мышление'
        }
        
        found_soft_lower = set()
        for keyword, skill_name in soft_keywords.items():
            if keyword in text_lower:
                skill_lower = skill_name.lower()
                if skill_lower not in found_soft_lower and skill_lower != 'аналит':
                    soft_skills.append(skill_name)
                    found_soft_lower.add(skill_lower)
        
        return hard_skills, soft_skills
    
    def _extract_jobs_v2(self, sections: Dict[str, str]) -> List:
        """Extract jobs from experience section"""
        jobs = []
        exp_text = sections['experience']
        lines = [l.strip() for l in exp_text.split('\n') if l.strip()]
        
        current_job = None
        job_id = 0
        pending_company = None  # Hold company name from previous line
        
        i = 0
        while i < len(lines):
            line = lines[i]
            line_lower = line.lower()
            
            company_keywords = ['т-банк', 'tcs', 'ozon', 'яндекс', 'google', 'sber', 'vk', 'mail', 'avito']
            job_titles = ['product manager', 'senior product', 'head of', 'manager', 'engineer', 'developer']
            achievement_verbs = ['запустил', 'разработал', 'провел', 'создал', 'увеличил', 'улучшил']
            
            is_company_line = any(kw in line_lower for kw in company_keywords)
            is_position_line = any(jt in line_lower for jt in job_titles) and not any(line_lower.startswith(v) for v in achievement_verbs)
            is_period = self._is_period_line(line)
            
            if is_company_line:
                # Save previous job
                if current_job and (current_job.responsibilities or current_job.achievements):
                    jobs.append(current_job)
                
                job_id += 1
                current_job = CandidateJob(id=job_id)
                
                # Parse company and position if comma-separated
                if ',' in line:
                    parts = line.split(',')
                    current_job.company_name = parts[0].strip()
                    current_job.position = parts[1].strip() if len(parts) > 1 else None
                else:
                    current_job.company_name = line
                    pending_company = line
            
            elif is_position_line and current_job:
                # Position line following company
                current_job.position = line
                pending_company = None
            
            elif is_period and current_job:
                # Period line
                current_job.period = line
            
            elif current_job and (line.startswith('-') or line.startswith('•')):
                # Bullet point
                text = line.lstrip('-•* ').strip()
                if len(text) > 5:
                    if len(text) > 60 or any(x in text.lower() for x in ['разви', 'провод', 'работ', 'отвеч', 'взаимодейств', 'форм', 'управ', 'запус']):
                        current_job.responsibilities.append(text)
                    else:
                        current_job.achievements.append(text)
            
            i += 1
        
        # Save last job
        if current_job and (current_job.responsibilities or current_job.achievements):
            jobs.append(current_job)
        
        return jobs
    
    def _extract_education_v2(self, sections: Dict[str, str]) -> List:
        """Extract education - only valid entries"""
        education = []
        edu_text = sections['education']
        
        # Look for pattern: "University, Degree, Field, Year"
        lines = [l.strip() for l in edu_text.split('\n') if l.strip() and len(l.strip()) > 10]
        
        for line in lines:
            # Look for year pattern
            year_match = re.search(r'\b(19|20)\d{2}\b', line)
            
            # If has year and reasonable length, treat as education entry
            if year_match:
                edu = EducationItem()
                
                # Try to parse institution and degree
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                    edu.institution = parts[0]
                    if len(parts) > 1:
                        edu.degree = parts[1]
                    if len(parts) > 2:
                        edu.year = parts[2]
                else:
                    edu.institution = line
                    edu.year = year_match.group()
                
                education.append(edu)
        
        return education
    
    def _extract_languages_v2(self, sections: Dict[str, str]) -> List[str]:
        """Extract languages from dedicated section"""
        lang_text = (sections['languages'] + ' ' + sections['header']).lower()
        languages = []
        
        # Known language patterns - with multiple aliases
        language_patterns = [
            (['русск', 'russian'], 'Русский'),
            (['english', 'англ'], 'Английский'),
            (['deutsch', 'немец'], 'Немецкий'),
            (['français', 'franç', 'франц'], 'Французский'),
            (['испан', 'spanish'], 'Испанский'),
            (['итал', 'italian'], 'Итальянский'),
            (['китай', 'chinese'], 'Китайский'),
            (['японск', 'japanese'], 'Японский'),
        ]
        
        found = set()
        for patterns, lang_name in language_patterns:
            for pattern in patterns:
                if pattern in lang_text:
                    if lang_name.lower() not in found:
                        languages.append(lang_name)
                        found.add(lang_name.lower())
                    break
        
        return languages
    
    def _extract_target_role_v2(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract target role from header section"""
        header = sections['header']
        
        # Look for lines containing role keywords
        for line in header.split('\n'):
            line_strip = line.strip()
            if not line_strip or len(line_strip) < 5:
                continue
            
            # Skip company names
            if any(x in line_strip.lower() for x in ['банк', 'ozon', 'яндекс', 'google']):
                continue
            
            # Check for role keywords
            if any(x in line_strip.lower() for x in ['product manager', 'manager', 'engineer', 'developer', 'менеджер']):
                # Remove section markers if present
                line_clean = line_strip.replace('ПРОФЕССИОНАЛЬНАЯ ЦЕЛЬ:', '').replace('CAREER GOAL:', '').strip()
                line_clean = line_clean.replace('ДОЛЖНОСТЬ:', '').replace('POSITION:', '').strip()
                if ':' in line_clean:
                    line_clean = line_clean.split(':', 1)[1].strip()
                return line_clean if line_clean else line_strip
        
        return None
    
    def _is_period_line(self, line: str) -> bool:
        """Check if line is a period (2019-2024 or 2019–2024)"""
        return bool(re.search(r'\d{4}[–\-]\d{4}', line))
    
    def parse_vacancy_profile(self, vacancy_text: str) -> VacancyProfile:
        """Extract vacancy profile with section-based parsing"""
        profile = VacancyProfile()
        
        # Split vacancy into sections
        sections = self._split_vacancy_into_sections(vacancy_text)
        
        # Extract basic info
        profile.role = self._extract_vacancy_role(sections)
        profile.seniority = self._extract_seniority(sections)
        profile.industry = self._extract_industry(sections)
        
        # Extract skills
        profile.must_have_skills = self._extract_must_have_skills(sections)
        profile.nice_to_have_skills = self._extract_nice_to_have_skills(sections)
        
        # Extract responsibilities
        profile.key_responsibilities = self._extract_key_responsibilities(sections)
        
        return profile
    
    def parse_vacancy(self, vacancy_text: str) -> VacancyProfile:
        """Alias for parse_vacancy_profile for API compatibility"""
        return self.parse_vacancy_profile(vacancy_text)
    
    def _split_vacancy_into_sections(self, text: str) -> Dict[str, str]:
        """Split vacancy by Russian section markers"""
        sections = {
            'header': '',
            'requirements': '',
            'responsibilities': '',
            'nice_to_have': '',
            'other': ''
        }
        
        lines = text.split('\n')
        current_section = 'header'
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Detect section headers (skip them)
            if any(x in line_lower for x in ['требование', 'requirement', 'must', 'must-have', 'навыки']):
                current_section = 'requirements'
                continue
            elif any(x in line_lower for x in ['задачи', 'обязанности', 'ответственност', 'responsibility', 'duties']):
                current_section = 'responsibilities'
                continue
            elif any(x in line_lower for x in ['будет плюсом', 'nice-to-have', 'nice to have', 'желатель', 'advantage']):
                current_section = 'nice_to_have'
                continue
            
            sections[current_section] += line + '\n'
        
        return sections
    
    def _extract_vacancy_role(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract job role from header"""
        header = sections['header']
        # Look for lines with job title keywords
        for line in header.split('\n')[:5]:
            line_strip = line.strip()
            if not line_strip:
                continue
            job_keywords = ['product manager', 'pm', 'manager', 'developer', 'engineer', 'analyst']
            if any(kw in line_strip.lower() for kw in job_keywords):
                # Remove section markers if present
                line_clean = line_strip.replace('ВАКАНСИЯ:', '').replace('VACANCY:', '').strip()
                line_clean = line_clean.replace('РОЛЬ:', '').replace('ROLE:', '').strip()
                if ':' in line_clean:
                    line_clean = line_clean.split(':', 1)[1].strip()
                return line_clean if line_clean else line_strip
        return "Position"
    
    def _extract_seniority(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract seniority level"""
        text = sections['header'] + ' ' + sections['requirements']
        seniority_keywords = {
            'senior': 'Senior',
            'старший': 'Senior',
            'middle': 'Middle',
            'миддл': 'Middle',
            'junior': 'Junior',
            'джун': 'Junior',
        }
        
        for keyword, level in seniority_keywords.items():
            if keyword in text.lower():
                return level
        return None
    
    def _extract_industry(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract industry from header/requirements"""
        text = (sections['header'] + ' ' + sections['requirements']).lower()
        industry_keywords = {
            'финтех': 'FinTech',
            'fintech': 'FinTech',
            'банк': 'Banking',
            'e-commerce': 'E-commerce',
            'tech': 'Technology',
            'saas': 'SaaS',
            'retail': 'Retail',
        }
        
        for keyword, industry in industry_keywords.items():
            if keyword in text:
                return industry
        return None
    
    def _extract_must_have_skills(self, sections: Dict[str, str]) -> List[str]:
        """Extract must-have skills from requirements section"""
        req_text = sections['requirements']
        skills = []
        found_skills = set()
        
        # First, extract explicit bullet points from requirements section
        for line in req_text.split('\n'):
            line_clean = line.strip().lstrip('-•* ').strip()
            if line_clean and len(line_clean) > 2:
                # Avoid duplicates (case-insensitive)
                if line_clean.lower() not in found_skills:
                    skills.append(line_clean)
                    found_skills.add(line_clean.lower())
        
        # Then try keyword matching for variations
        req_text_lower = (sections['requirements'] + ' ' + sections['header']).lower()
        
        keyword_map = {
            'sql': 'SQL',
            'a/b': 'A/B-тестирование',
            'a/b-тест': 'A/B-тестирование',
            'аналитик': 'Продуктовая аналитика',
            'юнит-эконом': 'Юнит-экономика',
            'финтех': 'FinTech опыт',
            'product manager': 'Product Manager',
            'pm': 'Product Manager',
            'стратег': 'Product Strategy',
            'метрик': 'Метрики',
        }
        
        for keyword, skill_name in keyword_map.items():
            if keyword in req_text_lower and skill_name.lower() not in found_skills:
                skills.append(skill_name)
                found_skills.add(skill_name.lower())
        
        return skills
    
    def _extract_nice_to_have_skills(self, sections: Dict[str, str]) -> List[str]:
        """Extract nice-to-have skills"""
        nice_text = sections['nice_to_have'].lower()
        skills = []
        
        skill_keywords = {
            'people management': 'People Management',
            'людьми': 'People Management',
            'ml': 'ML Basics',
            'машинное': 'ML Basics',
            'лидерство': 'Leadership',
            'архитектура': 'System Architecture',
        }
        
        found_skills = set()
        for keyword, skill in skill_keywords.items():
            if keyword in nice_text:
                if skill.lower() not in found_skills:
                    skills.append(skill)
                    found_skills.add(skill.lower())
        
        return skills
    
    def _extract_key_responsibilities(self, sections: Dict[str, str]) -> List[str]:
        """Extract key responsibilities"""
        resp_text = sections['responsibilities']
        
        responsibilities = []
        for line in resp_text.split('\n'):
            line = line.strip()
            if line and len(line) > 10:
                responsibilities.append(line)
        
        return responsibilities if responsibilities else []
    
    def build_strategy(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile
    ) -> StrategyBrief:
        """Build strategy for resume adaptation"""
        strategy = StrategyBrief()
        
        # Calculate fit score
        candidate_skills = set(s.lower() for s in candidate_profile.skills_hard)
        must_have = set(s.lower() for s in vacancy_profile.must_have_skills)
        
        match_count = len(candidate_skills & must_have)
        strategy.fit_score = min(0.95, 0.5 + (match_count / len(must_have) if must_have else 0) * 0.4)
        
        # Highlight all jobs (prioritize recent ones)
        strategy.highlight_job_ids = [job.id for job in candidate_profile.jobs]
        
        # Skills to highlight - matched skills
        matched_skills = []
        for skill in candidate_profile.skills_hard:
            if any(skill.lower() in m.lower() or m.lower() in skill.lower() for m in vacancy_profile.must_have_skills):
                matched_skills.append(skill)
        
        strategy.skills_to_highlight = matched_skills if matched_skills else candidate_profile.skills_hard[:5]
        
        # Gaps
        gaps = must_have - candidate_skills
        strategy.gaps = list(gaps)[:3] if gaps else []
        
        # Positioning
        vacancy_role = vacancy_profile.role or "Target Position"
        seniority = vacancy_profile.seniority or ""
        industry = vacancy_profile.industry or ""
        
        # Avoid duplicate seniority (if role already has it)
        seniority_part = ""
        if seniority and seniority.lower() not in vacancy_role.lower():
            seniority_part = seniority
        
        positioning_parts = [seniority_part, vacancy_role, f"в {industry}" if industry else None]
        strategy.positioning = " ".join([p for p in positioning_parts if p]).strip()
        
        # Recommendations
        if strategy.fit_score >= 0.8:
            strategy.recommendations_short = "Отличное совпадение. Выделите релевантный опыт и обязательные навыки."
        elif strategy.fit_score >= 0.6:
            strategy.recommendations_short = "Хорошее совпадение. Подчеркните переносимые навыки."
        else:
            strategy.recommendations_short = "Необходимо развитие. Выделите потенциал роста."
        
        return strategy
    
    def generate_resume(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        strategy_brief: StrategyBrief
    ) -> GeneratedResume:
        """Generate adapted resume"""
        
        # Build resume text
        resume_parts = []
        
        # Header
        resume_parts.append("=" * 70 + "\n")
        resume_parts.append("ПРОФЕССИОНАЛЬНОЕ РЕЗЮМЕ\n")
        resume_parts.append("=" * 70 + "\n\n")
        
        # Professional Summary
        resume_parts.append("ПРОФЕССИОНАЛЬНАЯ СВОДКА\n")
        if candidate_profile.target_role:
            resume_parts.append(f"Позиция: {candidate_profile.target_role}\n")
        if candidate_profile.experience_years:
            resume_parts.append(f"Опыт: {candidate_profile.experience_years} лет\n")
        if strategy_brief.positioning:
            resume_parts.append(f"Позиционирование: {strategy_brief.positioning}\n")
        resume_parts.append("\n")
        
        # Key Skills
        if candidate_profile.skills_hard:
            resume_parts.append("КЛЮЧЕВЫЕ НАВЫКИ\n")
            skills = strategy_brief.skills_to_highlight or candidate_profile.skills_hard[:8]
            resume_parts.append(", ".join(skills) + "\n\n")
        
        # Work Experience
        if candidate_profile.jobs:
            resume_parts.append("ОПЫТ РАБОТЫ\n")
            for job in candidate_profile.jobs:
                resume_parts.append("\n")
                if job.position:
                    resume_parts.append(f"{job.position}\n")
                if job.company_name:
                    resume_parts.append(f"Компания: {job.company_name}\n")
                if job.period:
                    resume_parts.append(f"Период: {job.period}\n")
                
                # Show real responsibilities
                for resp in job.responsibilities[:5]:
                    resume_parts.append(f"• {resp}\n")
                
                # Show achievements
                for ach in job.achievements[:2]:
                    resume_parts.append(f"✓ {ach}\n")
        
        resume_parts.append("\n")
        
        # Education - only valid entries
        valid_education = [e for e in candidate_profile.education if e.institution and len(e.institution) > 5]
        if valid_education:
            resume_parts.append("ОБРАЗОВАНИЕ\n")
            for edu in valid_education:
                if edu.institution:
                    resume_parts.append(f"• {edu.institution}\n")
                if edu.degree:
                    resume_parts.append(f"  Степень: {edu.degree}\n")
                if edu.year:
                    resume_parts.append(f"  Год: {edu.year}\n")
            resume_parts.append("\n")
        
        # Languages
        if candidate_profile.languages:
            resume_parts.append("ЯЗЫКИ\n")
            resume_parts.append(", ".join(candidate_profile.languages) + "\n")
        
        resume_text = "".join(resume_parts)
        
        # Generate technical report
        candidate_skills_lower = set(s.lower() for s in candidate_profile.skills_hard)
        must_haves = vacancy_profile.must_have_skills or []
        must_haves_lower = set(s.lower() for s in must_haves)
        
        covered = [m for m in must_haves if m.lower() in candidate_skills_lower or any(m.lower() in s.lower() for s in candidate_skills_lower)]
        uncovered = [m for m in must_haves if m.lower() not in candidate_skills_lower and not any(m.lower() in s.lower() for s in candidate_skills_lower)]
        
        report = TechnicalReport(
            highlighted_jobs=strategy_brief.highlight_job_ids,
            highlighted_skills=strategy_brief.skills_to_highlight,
            covered_must_haves=covered,
            uncovered_must_haves=uncovered,
            critic_warnings=[]
        )
        
        return GeneratedResume(
            title=f"Резюме для {vacancy_profile.role or 'позиции'}",
            resume_text=resume_text,
            technical_report=report
        )
