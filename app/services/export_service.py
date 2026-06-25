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
        explicit_path = os.getenv("RESUME_PDF_FONT_PATH", "").strip()
        candidates = [
            explicit_path,
            # Linux/Railway/common distro fonts.
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            # macOS local development fonts.
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]

        for path in candidates:
            if path and os.path.exists(path):
                return path

        preferred_names = (
            "DejaVuSans.ttf",
            "NotoSans-Regular.ttf",
            "NotoSerif-Regular.ttf",
            "LiberationSans-Regular.ttf",
            "FreeSans.ttf",
            "Arial.ttf",
        )
        found_by_name = {}
        for base_dir in ("/usr/share/fonts", "/usr/local/share/fonts"):
            for root, _, files in os.walk(base_dir):
                for file_name in files:
                    if file_name in preferred_names and file_name not in found_by_name:
                        found_by_name[file_name] = os.path.join(root, file_name)

        for font_name in preferred_names:
            if font_name in found_by_name:
                return found_by_name[font_name]

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
            font_path = ExportService._resolve_unicode_font_path()
            if not font_path:
                raise RuntimeError(
                    "No Unicode TTF font found for PDF export. "
                    "Install DejaVu/Noto/Liberation fonts or set RESUME_PDF_FONT_PATH."
                )

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
            logger.exception("Failed to generate PDF")
            raise RuntimeError("Failed to generate PDF") from e
    
    @staticmethod
    def format_json_nicely(data: dict) -> str:
        """Format JSON data for display"""
        import json
        return json.dumps(data, indent=2, ensure_ascii=False)
