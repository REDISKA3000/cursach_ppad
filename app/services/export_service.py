"""Export service for TXT and PDF"""
import logging
from typing import Optional
from io import BytesIO
from app.schemas.resume import GeneratedResume

logger = logging.getLogger(__name__)

class ExportService:
    """Export resume in various formats"""
    
    @staticmethod
    def export_txt(generated_resume: GeneratedResume) -> str:
        """Export resume as TXT"""
        return generated_resume.resume_text
    
    @staticmethod
    def export_pdf(generated_resume: GeneratedResume) -> bytes:
        """Export resume as PDF"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            story = []
            
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=14,
                textColor='#000000',
                spaceAfter=12,
                alignment=1  # center
            )
            
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontSize=10,
                leading=12,
            )
            
            # Add title
            story.append(Paragraph(generated_resume.title, title_style))
            story.append(Spacer(1, 0.3*inch))
            
            # Add resume text
            for line in generated_resume.resume_text.split('\n'):
                if line.strip():
                    story.append(Paragraph(line, body_style))
                else:
                    story.append(Spacer(1, 0.1*inch))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            # Fallback: return text as UTF-8 encoded bytes
            return generated_resume.resume_text.encode('utf-8')
    
    @staticmethod
    def format_json_nicely(data: dict) -> str:
        """Format JSON data for display"""
        import json
        return json.dumps(data, indent=2, ensure_ascii=False)
