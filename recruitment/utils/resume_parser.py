"""
resume_parser.py
----------------
Utilities for extracting text from PDF/DOCX resumes and parsing
structured information (skills, experience, education) from that text.

Dependencies: PyMuPDF (fitz), python-docx, re
"""
import os
import re

# ---------------------------------------------------------------------------
# A curated list of common technical & soft skills.  Case-insensitive match
# against the raw resume text determines which skills are detected.
# ---------------------------------------------------------------------------
SKILL_KEYWORDS = [
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "c", "go",
    "golang", "rust", "ruby", "php", "swift", "kotlin", "scala", "r",
    "matlab", "perl", "bash", "shell", "powershell", "vba",
    # Web
    "html", "css", "react", "reactjs", "angular", "vue", "vuejs", "nextjs",
    "nodejs", "node.js", "express", "django", "flask", "fastapi", "spring",
    "springboot", "laravel", "rails", "asp.net", "graphql", "rest api",
    "restful", "soap", "websocket",
    # Data / AI / ML
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn", "pandas",
    "numpy", "scipy", "matplotlib", "seaborn", "tableau", "power bi",
    "data analysis", "data science", "data engineering", "etl", "spark",
    "hadoop", "airflow", "kafka", "dbt", "sql", "mysql", "postgresql",
    "sqlite", "mongodb", "redis", "elasticsearch", "cassandra",
    # Cloud / DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
    "terraform", "ansible", "jenkins", "github actions", "ci/cd", "linux",
    "git", "github", "gitlab", "bitbucket", "nginx", "apache",
    # Mobile
    "android", "ios", "flutter", "react native", "xamarin",
    # Testing
    "selenium", "pytest", "junit", "jest", "cypress", "postman",
    # Project / Soft
    "agile", "scrum", "kanban", "jira", "confluence", "excel",
    "communication", "leadership", "problem solving", "teamwork",
]

# Degree pattern for education extraction
_DEGREE_PATTERN = re.compile(
    r"(b\.?tech|b\.?e\.?|b\.?sc|m\.?tech|m\.?sc|m\.?e\.?|mba|ph\.?d|"
    r"bachelor(?:\'s)?|master(?:\'s)?|m\.?s\.?|b\.?s\.?|associate)",
    re.IGNORECASE,
)

# Experience year pattern: "3 years", "5+ years of experience", etc.
_EXP_PATTERN = re.compile(
    r"(\d+)\+?\s*(?:-\s*\d+\s*)?years?\s*(?:of\s*)?(?:experience|exp\.?|work)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------

def extract_text_from_resume(file_path: str) -> str:
    """
    Extract raw text from a resume file.

    Supports:
      - PDF  (via PyMuPDF / fitz)
      - DOCX (via python-docx)

    Returns an empty string on unsupported formats or errors.
    """
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text

        elif ext in (".docx", ".doc"):
            from docx import Document
            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)

        else:
            return ""

    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Structured Parsing
# ---------------------------------------------------------------------------

def _extract_skills(text: str) -> list[str]:
    """Return list of detected skill keywords present in the text."""
    text_lower = text.lower()
    found = []
    for skill in SKILL_KEYWORDS:
        # whole-word / phrase match to avoid false positives
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill.title())
    return found


def _extract_experience_years(text: str) -> int | None:
    """Return the largest number of years of experience found, or None."""
    matches = _EXP_PATTERN.findall(text)
    if not matches:
        return None
    return max(int(m) for m in matches)


def _extract_education(text: str) -> str:
    """
    Return the first line that contains a degree keyword, cleaned up.
    Falls back to empty string.
    """
    for line in text.splitlines():
        if _DEGREE_PATTERN.search(line):
            cleaned = line.strip()
            if 5 < len(cleaned) < 250:
                return cleaned
    return ""


def parse_resume(file_path: str) -> dict:
    """
    Parse a resume file and return a structured dict:

    {
        "raw_text":             str,
        "skills":               list[str],   # detected skill keywords
        "experience_years":     int | None,
        "education":            str,
    }
    """
    raw_text = extract_text_from_resume(file_path)

    return {
        "raw_text": raw_text,
        "skills": _extract_skills(raw_text),
        "experience_years": _extract_experience_years(raw_text),
        "education": _extract_education(raw_text),
    }
