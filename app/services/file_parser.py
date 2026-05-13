"""File parsing utilities"""
import importlib
import logging
import os
import sys

logger = logging.getLogger(__name__)

class FileParser:
    """Parse uploaded files"""

    @staticmethod
    def _load_optional_module(module_name: str):
        """Load optional parser dependency from venv or bundled Codex runtime."""
        try:
            return importlib.import_module(module_name)
        except ImportError:
            bundled_root = os.path.expanduser(
                "~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python"
            )
            candidate_paths = [bundled_root]

            lib_dir = os.path.join(bundled_root, "lib")
            if os.path.isdir(lib_dir):
                for child in os.listdir(lib_dir):
                    site_packages = os.path.join(lib_dir, child, "site-packages")
                    if os.path.isdir(site_packages):
                        candidate_paths.append(site_packages)

            for path in candidate_paths:
                if os.path.isdir(path) and path not in sys.path:
                    sys.path.append(path)
                    try:
                        return importlib.import_module(module_name)
                    except ImportError:
                        continue
        return None

    @staticmethod
    def _normalize_pdf_text(text: str) -> str:
        """Clean noisy PDF extraction artifacts while preserving structure."""
        if not text:
            return ""

        text = text.replace("\xa0", " ")
        text = text.replace("\u200b", "")
        text = text.replace("\r", "\n")
        text = text.replace("Резюме обновлено", "\nРезюме обновлено")
        text = text.replace("Гладилин Егор  •  Резюме обновлено", "\nГладилин Егор  •  Резюме обновлено")
        text = "\n".join(line.rstrip() for line in text.splitlines())
        return text.strip()
    
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
            pypdf = FileParser._load_optional_module("pypdf")
            if pypdf:
                reader = pypdf.PdfReader(file_path)
                text = "\n".join((page.extract_text() or "") for page in reader.pages)
                return FileParser._normalize_pdf_text(text)

            pypdf2 = FileParser._load_optional_module("PyPDF2")
            if pypdf2:
                with open(file_path, 'rb') as f:
                    reader = pypdf2.PdfReader(f)
                    text = "\n".join((page.extract_text() or "") for page in reader.pages)
                    return FileParser._normalize_pdf_text(text)

            logger.warning("No PDF parser installed, skipping PDF parsing")
            return ""
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            return ""
    
    @staticmethod
    def parse_docx(file_path: str) -> str:
        """Parse DOCX file (best effort)"""
        try:
            docx = FileParser._load_optional_module("docx")
            if not docx:
                logger.warning("python-docx not installed, skipping DOCX parsing")
                return ""

            Document = docx.Document
            doc = Document(file_path)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text
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
