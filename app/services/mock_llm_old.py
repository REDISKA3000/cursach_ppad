"""Mock LLM provider for demo mode"""
import json
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
            
            # Detect section headers
            if any(x in line_lower for x in ['опыт работы', 'work experience', 'профессиональный опыт']):
                current_section = 'experience'
            elif any(x in line_lower for x in ['навыки:', 'skill', 'ключевые навыки', 'компетенции']):
                current_section = 'skills'
            elif any(x in line_lower for x in ['образование:', 'education', 'учебное']):
                current_section = 'education'
            elif any(x in line_lower for x in ['язык', 'language', 'иностранные']):
                current_section = 'languages'
            else:
                # Accumulate line in current section
                sections[current_section] += line + '\n'
        
        return sections
    
    def _extract_experience_years_v2(self, sections: Dict[str, str]) -> Optional[int]:
        """Extract experience years from header + experience sections"""
        import re
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
        
        # Comprehensive keyword matching
        tech_keywords = {
            # Programming
            'python': 'Python', 'javascript': 'JavaScript', 'java': 'Java', 
            'sql': 'SQL', 'react': 'React', 'angular': 'Angular',
            # Product/Business
            'a/b': 'A/B-тесты', 'a/b-test': 'A/B-тесты', 'ab-test': 'A/B-тесты',
            'a/b-тест': 'A/B-тесты', 'a/b-тестирование': 'A/B-тесты',
            'аналитика': 'Продуктовая аналитика', 'аналитик': 'Продуктовая аналитика',
            'юнит-экономика': 'Юнит-экономика', 'юнит экономика': 'Юнит-экономика',
            'метрика': 'Продуктовая аналитика',
            'cjm': 'CJM', 'customer journey': 'CJM',
            'backlog': 'Backlog management', 'бэклог': 'Backlog management',
            'growth': 'Growth', 'грасс': 'Growth', 'монетизация': 'Монетизация',
            'retention': 'Retention', 'ретеншн': 'Retention',
            'onboarding': 'Onboarding', 'онбординг': 'Onboarding',
            'product strategy': 'Product Strategy', 'стратегия продукта': 'Product Strategy',
            'product manager': 'Product Manager', 'product owner': 'Product Owner'
        }
        
        # Extract skills - deduplicate case-insensitive
        found_skills = set()
        for keyword, skill_name in tech_keywords.items():
            if keyword in text_lower:
                skill_lower = skill_name.lower()
                if skill_lower not in found_skills:
                    hard_skills.append(skill_name)
                    found_skills.add(skill_lower)
        
        # Explicit skills section parsing
        skills_section = sections['skills']
        if skills_section:
            for line in skills_section.split(','):
                skill = line.strip()
                if len(skill) >= 2 and skill.lower() not in found_skills:
                    hard_skills.append(skill)
                    found_skills.add(skill.lower())
        
        # Soft skills
        soft_keywords = {
            'коммуникация': 'Коммуникация',
            'лидерство': 'Лидерство',
            'teamwork': 'Командная работа',
            'аналитическое': 'Аналитическое мышление'
        }
        
        found_soft = set()
        for keyword, skill_name in soft_keywords.items():
            if keyword in text_lower:
                skill_lower = skill_name.lower()
                if skill_lower not in found_soft:
                    soft_skills.append(skill_name)
                    found_soft.add(skill_lower)
        
        return list(hard_skills), list(soft_skills)
    
    def _extract_jobs_v2(self, sections: Dict[str, str]) -> List:
        """Extract jobs from experience section"""
        from app.schemas.candidate import CandidateJob
        
        jobs = []
        exp_text = sections['experience']
        lines = [l.strip() for l in exp_text.split('\n') if l.strip()]
        
        current_job = None
        job_id = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check if it looks like a job header (company name + position or just company)
            company_keywords = ['т-банк', 'ozon', 'яндекс', 'google', 'sber', 'vk', 'mail', 'avito']
            line_lower = line.lower()
            
            is_header = False
            company = None
            position = None
            
            # Pattern 1: "Company (TCS Bank), Position"
            if any(kw in line_lower for kw in company_keywords):
                is_header = True
                # Try to parse company and position
                if ',' in line:
                    parts = line.split(',')
                    company = parts[0].strip()
                    position = parts[1].strip() if len(parts) > 1 else None
                else:
                    company = line
            
            # Pattern 2: Position like "Product Manager" or "Senior Product Manager / Head"
            job_titles = ['product manager', 'senior product', 'head of', 'manager', 'engineer', 'developer']
            if not is_header and any(jt in line_lower for jt in job_titles):
                # Check if it's not an achievement (doesn't start with verb)
                achievement_verbs = ['запустил', 'разработал', 'провел', 'создал', 'увеличил', 'улучшил']
                if not any(line_lower.startswith(v) for v in achievement_verbs):
                    is_header = True
                    position = line
            
            if is_header:
                # Save previous job
                if current_job and (current_job.responsibilities or current_job.achievements):
                    jobs.append(current_job)
                
                job_id += 1
                current_job = CandidateJob(id=job_id)
                current_job.company_name = company
                current_job.position = position
                
                # Check next line for period
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if self._is_period_line(next_line):
                        current_job.period = next_line
                        i += 1
            
            elif current_job and (line.startswith('-') or line.startswith('•')):
                # Bullet point
                text = line.lstrip('-•* ').strip()
                if len(text) > 5:
                    # Heuristic: long text = responsibility, short = achievement
                    if len(text) > 60 or any(x in text.lower() for x in [
                        'разви', 'провод', 'работ', 'отвеч', 'взаимодейств', 'форм', 'управ', 'запус'
                    ]):
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
        from app.schemas.candidate import EducationItem
        
        education = []
        edu_text = sections['education']
        
        # Look for pattern: "University, Degree, Field, Year"
        lines = [l.strip() for l in edu_text.split('\n') if l.strip()]
        
        for line in lines:
            # Skip empty or too short lines
            if len(line) < 10:
                continue
            
            # Look for year pattern
            import re
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
        import re
        
        lang_text = sections['languages'].lower()
        languages = []
        
        # Known language patterns
        patterns = {
            'русск': 'Русский',
            'english': 'Английский',
            'english': 'English',
            'deutsch': 'Немецкий',
            'français': 'Французский',
        }
        
        for pattern, lang in patterns.items():
            if pattern in lang_text:
                if lang not in languages:
                    languages.append(lang)
        
        if not languages:
            # Check header for language hints
            if 'english' in sections['header'].lower():
                languages.append('English')
            if 'русск' in sections['header'].lower():
                languages.append('Russian')
        
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
                return line_strip
        
        return None
    
    def _is_period_line(self, line: str) -> bool:
        """Check if line is a period (2019-2024 or 2019–2024)"""
        import re
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
            
            # Detect section headers
            if any(x in line_lower for x in ['требование', 'requirement', 'must', 'must-have', 'навыки']):
                current_section = 'requirements'
            elif any(x in line_lower for x in ['задачи', 'обязанности', 'ответственност', 'responsibility']):
                current_section = 'responsibilities'
            elif any(x in line_lower for x in ['будет плюсом', 'nice-to-have', 'nice to have', 'желатель']):
                current_section = 'nice_to_have'
            else:
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
                return line_strip
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
        req_text = sections['requirements'].lower()
        skills = []
        
        # Keywords to look for
        skill_keywords = {
            'sql': 'SQL',
            'a/b': 'A/B-тестирование',
            'a/b-тест': 'A/B-тестирование',
            'аналитика': 'Продуктовая аналитика',
            'юнит-экономика': 'Юнит-экономика',
            'юнит экономика': 'Юнит-экономика',
            'финтех': 'Опыт в FinTech',
            'product manager': 'Product Manager',
            'pm': 'Product Manager',
            'стратег': 'Product Strategy',
            'метрик': 'Метрики и аналитика',
        }
        
        found_skills = set()
        for keyword, skill in skill_keywords.items():
            if keyword in req_text:
                if skill.lower() not in found_skills:
                    skills.append(skill)
                    found_skills.add(skill.lower())
        
        # Extract years requirement if present
        import re
        match = re.search(r'(\d+)\s*(?:год|лет|years?)', req_text)
        if match:
            years = match.group(1)
            exp_skill = f"Опыт {years}+ лет"
            if exp_skill.lower() not in found_skills:
                skills.append(exp_skill)
                found_skills.add(exp_skill.lower())
        
        return skills if skills else []
    
    def _extract_nice_to_have_skills(self, sections: Dict[str, str]) -> List[str]:
        """Extract nice-to-have skills"""
        nice_text = sections['nice_to_have'].lower()
        skills = []
        
        skill_keywords = {
            'people management': 'People Management',
            'людьми': 'People Management',
            'ml': 'ML Basic',
            'машинное': 'ML Basic',
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
        if "навык" in text_lower or "skill" in text_lower:
            lines = text.split('\n')
            in_skills = False
            for line in lines:
                if "навык" in line.lower() or "skill" in line.lower():
                    in_skills = True
                    continue
                if in_skills:
                    if any(x in line.lower() for x in ["образ", "язык", "опыт", "work", "experience"]):
                        break
                    # Parse comma-separated skills
                    for skill in line.split(','):
                        skill = skill.strip()
                        if len(skill) >= 2:
                            hard_skills.append(skill)
        
        # Soft skills
        soft_keywords = ["общение", "коммуникаци", "лидерств", "руководств", "teamwork", "team", 
                        "problem-solving", "time management", "adaptabil", 
                        "critical thinking", "аналит"]
        
        for keyword in soft_keywords:
            if keyword in text_lower:
                if "лидерств" in keyword or "руководств" in keyword:
                    soft_skills.append("Лидерство")
                elif "общени" in keyword or "коммуникаци" in keyword:
                    soft_skills.append("Коммуникация")
                elif "team" in keyword:
                    soft_skills.append("Командная работа")
                else:
                    soft_skills.append(keyword.title())
        
        # Remove duplicates
        hard_skills = list(set(hard_skills))
        soft_skills = list(set(soft_skills))
        
        return hard_skills, soft_skills
    
    def _extract_jobs(self, text: str) -> List[CandidateJob]:
        """Extract job entries with better structure detection"""
        jobs = []
        lines = text.split('\n')
        
        current_job = None
        job_id = 0
        pending_header_lines = []  # Lines that might form a header
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Skip section headers
            if any(x in line.lower() for x in ['опыт работы', 'work experience', 'образование', 'education', 
                                               'навык', 'skill', 'язык', 'language', 'сертификат', 'certificate']):
                # Save previous job if exists
                if current_job and (current_job.responsibilities or current_job.achievements):
                    jobs.append(current_job)
                current_job = None
                pending_header_lines = []
                i += 1
                continue
            
            # Bullet point - add to current job
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                bullet_text = line.lstrip('-•* ').strip()
                if bullet_text and len(bullet_text) > 5:
                    if current_job:
                        # Heuristic: determine if it's responsibility or achievement
                        if len(bullet_text) > 60 or any(x in bullet_text.lower() for x in 
                            ['разви', 'провод', 'работ', 'отвеч', 'взаимодейств', 'форм', 'писа', 'анали', 'управля', 'запус', 'постро']):
                            current_job.responsibilities.append(bullet_text)
                        else:
                            current_job.achievements.append(bullet_text)
                i += 1
                continue
            
            # Non-bullet line - could be job header
            # Check if it looks like a company name or position
            is_company_or_position = self._looks_like_job_header(line)
            is_period = self._is_period_line(line)
            
            if is_company_or_position or is_period:
                pending_header_lines.append((line, is_period))
                i += 1
                
                # Look ahead to see if we have more header lines
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        i += 1
                        continue
                    if next_line.startswith('-') or next_line.startswith('•') or next_line.startswith('*'):
                        # End of header, start of content
                        break
                    if self._looks_like_job_header(next_line) or self._is_period_line(next_line):
                        pending_header_lines.append((next_line, self._is_period_line(next_line)))
                        i += 1
                    else:
                        # Line doesn't look like header - might be achievement
                        break
                
                # Now process accumulated header lines
                if pending_header_lines:
                    # Save previous job
                    if current_job and (current_job.responsibilities or current_job.achievements):
                        jobs.append(current_job)
                    
                    job_id += 1
                    current_job = CandidateJob(id=job_id)
                    
                    # Parse header lines
                    company_name = None
                    position = None
                    
                    for hline, is_per in pending_header_lines:
                        if is_per:
                            current_job.period = hline
                        else:
                            # Try to parse as company + position
                            comp, pos = self._parse_company_position(hline)
                            if comp:
                                company_name = comp
                            if pos:
                                position = pos
                    
                    current_job.company_name = company_name
                    current_job.position = position or (pending_header_lines[0][0] if pending_header_lines else None)
                    pending_header_lines = []
            else:
                # Line doesn't look like header - ignore or save it  
                pending_header_lines = []
                i += 1
        
        # Save last job
        if current_job and (current_job.responsibilities or current_job.achievements):
            jobs.append(current_job)
        
        return jobs
    
    def _looks_like_job_header(self, line: str) -> bool:
        """Check if line looks like a company name or position"""
        if not line or len(line) < 3:
            return False
        
        line_lower = line.lower()
        
        # Known company names
        company_keywords = ["банк", "яндекс", "google", "amazon", "microsoft", "facebook", 
                           "ozon", "avito", "sber", "vk", "mail", "yandex", "компани"]
        
        # Job titles that indicate positions
        job_titles = ["product manager", "pm", "developer", "engineer", "analyst", "lead", 
                     "specialist", "architect", "менеджер", "разработчик", "аналитик", 
                     "лид", "специалист", "инженер", "архитектор", "senior", "junior", 
                     "head of", "head", "директор", "начальник", "руководитель"]
        
        # Check for company keyword
        for kw in company_keywords:
            if kw in line_lower:
                return True
        
        # Check for position keyword (but avoid phrases that are clearly achievements)
        # Achievements often start with verbs: провел, запустил, разработал, etc.
        achievement_verbs = ["провел", "запустил", "разработал", "создал", "реализовал", 
                            "выполнил", "осуществил", "анализировал", "увеличил", "улучшил",
                            "реорганизовал", "отвечал", "контролировал"]
        
        starts_with_verb = any(line_lower.startswith(verb) for verb in achievement_verbs)
        
        if starts_with_verb:
            return False  # This looks like an achievement, not a job header
        
        for jt in job_titles:
            if jt in line_lower:
                return True
        
        # Check if line is structurally a position (short, contains role keywords)
        # But exclude if it's very long (likely an achievement bullet without dash)
        if len(line) < 100 and ('/' in line or ' и ' in line_lower or '-' in line):
            # Could be position like "Senior PM / Head of Product" or "Manager - Sales"
            return any(x in line_lower for x in job_titles + ['/'])
        
        return False

    
    def _is_period_line(self, line: str) -> bool:
        """Check if line is a period (2019-2024 or 2019–2024)"""
        import re
        return bool(re.search(r'\d{4}[–\-]\d{4}', line))
    
    def _parse_company_position(self, line: str) -> tuple[Optional[str], Optional[str]]:
        """Parse company and position from a line"""
        # Format: "Company, Position" or "Position, Company"
        if ',' in line:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                return parts[0], parts[1]
        
        # Try to extract company name and position
        company_keywords = ["банк", "яндекс", "google", "amazon", "microsoft", "facebook", 
                           "ozon", "avito", "sber", "vk", "mail", "yandex"]
        
        for kw in company_keywords:
            if kw in line.lower():
                # Split by the keyword
                idx = line.lower().find(kw)
                company = line[:idx + len(kw)].strip()
                position = line[idx + len(kw):].strip(', ').title()
                return company, position or None
        
        # If can't parse, return whole line as position
        return None, line
    
    def _extract_target_role(self, lines: list, jobs: List[CandidateJob]) -> Optional[str]:
        """Extract target role from first relevant line"""
        for line in lines[:10]:
            line_lower = line.lower()
            # Skip empty or too short lines
            if len(line) < 5:
                continue
            # Skip lines that are company names or already jobs
            if any(x in line_lower for x in ["банк", "яндекс", "ozon", "avito"]):
                continue
            # Look for role-like lines
            if any(x in line_lower for x in ["manager", "developer", "engineer", "product", "менеджер", "разработчик"]):
                return line
        
        # Return most recent job title
        if jobs and jobs[0].position:
            return jobs[0].position
        
        return None
    
    def _extract_education(self, text: str) -> List[EducationItem]:
        """Extract education"""
        education = []
        
        edu_keywords = ["university", "institute", "school", "academy", 
                       "университет", "институт", "школа", "академия",
                       "bs", "ba", "ms", "ma", "phd", "бакалавр", "магистр"]
        
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in edu_keywords):
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if any(kw in line.lower() for kw in edu_keywords):
                    edu = EducationItem(institution=line.strip())
                    
                    # Try to find degree in next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if any(x in next_line.lower() for x in ["degree", "бакалавр", "магистр", "specialist"]):
                            edu.degree = next_line
                    
                    education.append(edu)
        
        return education
    
    def _extract_languages(self, text: str) -> List[str]:
        """Extract languages"""
        languages = []
        
        lang_keywords = ["english", "русский", "french", "german", "spanish", 
                        "chinese", "japanese", "arabic", "portuguese",
                        "английск", "французск", "немецк", "испанск", "китайск"]
        
        text_lower = text.lower()
        
        for lang in lang_keywords:
            if lang in text_lower:
                if "english" in lang or "английск" in lang:
                    languages.append("English")
                elif "русск" in lang:
                    languages.append("Russian")
                elif "french" in lang or "французск" in lang:
                    languages.append("French")
                elif "german" in lang or "немецк" in lang:
                    languages.append("German")
                else:
                    languages.append(lang.title())
        
        return list(set(languages))
    
    def parse_vacancy(self, vacancy_text: str) -> VacancyProfile:
        """Extract vacancy profile from job posting"""
        profile = VacancyProfile()
        
        # Try to extract role from first lines
        lines = vacancy_text.split('\n')
        for line in lines[:5]:
            if line.strip() and len(line) > 5:
                profile.role = line.strip()[:100]
                break
        
        if not profile.role:
            profile.role = "Software Position"
        
        # Extract skills
        tech_keywords = ["python", "javascript", "java", "sql", "react", "angular", "aws",
                        "docker", "kubernetes", "git", "api", "rest", "graphql", "database"]
        
        lower_text = vacancy_text.lower()
        for keyword in tech_keywords:
            if keyword in lower_text:
                if "required" in lower_text or "must" in lower_text:
                    profile.must_have_skills.append(keyword.upper())
                else:
                    profile.nice_to_have_skills.append(keyword.upper())
        
        # Ensure at least some skills
        if not profile.must_have_skills:
            profile.must_have_skills = ["Problem Solving", "Communication"]
        if not profile.nice_to_have_skills:
            profile.nice_to_have_skills = ["Project Management", "Mentoring"]
        
        # Extract responsibilities
        for line in lines:
            if any(word in line.lower() for word in ["responsible", "will", "duties", "tasks"]):
                if len(line) > 10:
                    profile.key_responsibilities.append(line.strip()[:100])
        
        if not profile.key_responsibilities:
            profile.key_responsibilities = ["Core responsibility 1", "Core responsibility 2"]
        
        # Keywords for ATS
        profile.keywords_for_ats = profile.must_have_skills + profile.nice_to_have_skills
        
        profile.raw_warnings.append("Vacancy parsed using heuristics (mock mode)")
        
        return profile
    
    def build_strategy(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        candidate_preferences: Optional[Dict[str, Any]] = None
    ) -> StrategyBrief:
        """Build career strategy"""
        strategy = StrategyBrief()
        
        # Calculate fit score
        candidate_skills = set(candidate_profile.skills_hard)
        must_have = set(vacancy_profile.must_have_skills)
        
        if must_have:
            match_count = len(candidate_skills & must_have)
            strategy.fit_score = min(0.95, 0.5 + (match_count / len(must_have)) * 0.4)
        else:
            strategy.fit_score = 0.6
        
        # Highlight first job or all if multiple
        strategy.highlight_job_ids = [job.id for job in candidate_profile.jobs]
        strategy.downplay_job_ids = []
        
        # Skills to highlight
        strategy.skills_to_highlight = list(candidate_skills & must_have)
        if not strategy.skills_to_highlight:
            strategy.skills_to_highlight = candidate_profile.skills_hard[:3]
        
        # Soft skills to soften
        strategy.skills_to_soften = candidate_profile.skills_soft[:1] if candidate_profile.skills_soft else []
        
        # Gaps
        gaps = must_have - candidate_skills
        strategy.gaps = list(gaps)[:3] if gaps else []
        
        # Resume variants
        strategy.resume_variants = ["Standard Format", "Functional Format", "Chronological Format"]
        
        # Positioning
        vacancy_role = vacancy_profile.role or "Target Position"
        strategy.positioning = f"Position as strong candidate for {vacancy_role} role"
        
        # Recommendations
        if strategy.fit_score >= 0.8:
            strategy.recommendations_short = "Strong fit. Focus on highlighting relevant experience and must-have skills."
        elif strategy.fit_score >= 0.6:
            strategy.recommendations_short = "Moderate fit. Emphasize transferable skills and domain knowledge."
        else:
            strategy.recommendations_short = "Development opportunity. Highlight growth potential and relevant skills."
        
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
        resume_parts.append("=== PROFESSIONAL RESUME ===\n")
        
        # Professional Summary
        target_role = strategy_brief.positioning or "Professional"
        resume_parts.append(f"PROFESSIONAL SUMMARY\n")
        resume_parts.append(f"Experienced professional with {candidate_profile.experience_years or 3} years of experience.\n")
        resume_parts.append(f"Targeting: {target_role}\n\n")
        
        # Key Skills
        resume_parts.append("KEY SKILLS\n")
        highlighted_skills = strategy_brief.skills_to_highlight or candidate_profile.skills_hard[:5]
        resume_parts.append(", ".join(highlighted_skills) + "\n\n")
        
        # Work Experience
        resume_parts.append("WORK EXPERIENCE\n")
        for job in candidate_profile.jobs:
            resume_parts.append(f"\n{job.position or 'Position'}\n")
            if job.company_name:
                resume_parts.append(f"Company: {job.company_name}\n")
            if job.period:
                resume_parts.append(f"Period: {job.period}\n")
            for resp in job.responsibilities[:3]:
                resume_parts.append(f"• {resp}\n")
            for ach in job.achievements[:2]:
                resume_parts.append(f"✓ {ach}\n")
        
        resume_parts.append("\n")
        
        # Education
        if candidate_profile.education:
            resume_parts.append("EDUCATION\n")
            for edu in candidate_profile.education:
                if edu.institution:
                    resume_parts.append(f"{edu.institution}\n")
                if edu.degree:
                    resume_parts.append(f"Degree: {edu.degree}\n")
                if edu.year:
                    resume_parts.append(f"Year: {edu.year}\n")
        
        resume_text = "".join(resume_parts)
        
        # Generate technical report
        report = TechnicalReport(
            highlighted_jobs=strategy_brief.highlight_job_ids,
            highlighted_skills=strategy_brief.skills_to_highlight,
            covered_must_haves=list(set(candidate_profile.skills_hard) & set(vacancy_profile.must_have_skills)),
            uncovered_must_haves=strategy_brief.gaps,
            critic_warnings=["Generated in mock mode - verify all information"]
        )
        
        return GeneratedResume(
            title=f"Resume for {vacancy_profile.role or 'Position'}",
            resume_text=resume_text,
            technical_report=report
        )
