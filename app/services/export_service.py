"""Export service for TXT and PDF"""
import logging
import os
from io import BytesIO
from xml.sax.saxutils import escape
from app.schemas.resume import GeneratedResume

logger = logging.getLogger(__name__)

class ExportService:
    """Export resume in various formats"""

    @staticmethod
    def _resolve_unicode_font_path() -> str | None:
        """Pick a local TTF font with Cyrillic support for PDF export."""
        candidates = [
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Helvetica.ttc",
        ]

        for path in candidates:
            if os.path.exists(path):
                return path

        return None
    
    @staticmethod
    def export_txt(generated_resume: GeneratedResume) -> str:
        """Export resume as TXT"""
        return generated_resume.resume_text
    
    @staticmethod
    def export_pdf(generated_resume: GeneratedResume) -> bytes:
        """Export resume as PDF"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=48,
                rightMargin=48,
                topMargin=48,
                bottomMargin=48,
            )
            story = []
            
            styles = getSampleStyleSheet()
            font_name = "Helvetica"
            font_path = ExportService._resolve_unicode_font_path()
            if font_path:
                font_name = "ResumeUnicode"
                if font_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(font_name, font_path))

            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=font_name,
                fontSize=14,
                textColor='#000000',
                spaceAfter=12,
                alignment=1  # center
            )
            
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontName=font_name,
                fontSize=10,
                leading=13,
                spaceAfter=4,
            )

            heading_style = ParagraphStyle(
                'SectionHeading',
                parent=body_style,
                fontName=font_name,
                fontSize=11,
                leading=14,
                spaceBefore=8,
                spaceAfter=6,
            )
            
            # Add title
            story.append(Paragraph(escape(generated_resume.title), title_style))
            story.append(Spacer(1, 0.2 * inch))
            
            # Add resume text
            for line in generated_resume.resume_text.split('\n'):
                stripped = line.strip()
                if stripped:
                    safe_line = escape(stripped).replace("•", "&#8226;")
                    if stripped.startswith("="):
                        continue
                    if stripped.isupper() and len(stripped) < 80:
                        story.append(Paragraph(safe_line, heading_style))
                    else:
                        story.append(Paragraph(safe_line, body_style))
                else:
                    story.append(Spacer(1, 0.08 * inch))
            
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
