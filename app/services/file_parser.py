"""File parsing utilities"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class FileParser:
    """Parse uploaded files"""
    
    @staticmethod
    def parse_txt(file_path: str) -> str:
        """Read text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read text file: {e}")
            return ""
    
    @staticmethod
    def parse_pdf(file_path: str) -> str:
        """Parse PDF file (best effort)"""
        try:
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text()
            return text
        except ImportError:
            logger.warning("PyPDF2 not installed, skipping PDF parsing")
            return ""
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            return ""
    
    @staticmethod
    def parse_docx(file_path: str) -> str:
        """Parse DOCX file (best effort)"""
        try:
            from docx import Document
            doc = Document(file_path)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text
        except ImportError:
            logger.warning("python-docx not installed, skipping DOCX parsing")
            return ""
        except Exception as e:
            logger.error(f"Failed to parse DOCX: {e}")
            return ""
    
    @staticmethod
    def parse_file(file_path: str) -> str:
        """Parse file based on extension"""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext == '.txt':
            return FileParser.parse_txt(file_path)
        elif ext == '.pdf':
            return FileParser.parse_pdf(file_path)
        elif ext == '.docx':
            return FileParser.parse_docx(file_path)
        else:
            logger.warning(f"Unsupported file format: {ext}")
            return ""
