"""
api.py — FairHire AI Utilities · FastAPI microservice
======================================================
Exposes the four pure-Python utility modules as REST endpoints.

Endpoints
---------
POST /parse-resume    → recruitment.utils.resume_parser.parse_resume
POST /score-match     → recruitment.utils.match_scorer  (component functions)
POST /evaluate-bias   → recruitment.utils.bias_agent    (_EVALUATORS dispatch)
POST /detect-bias     → recruitment.utils.bias_detector.scan_job_description

Run
---
    python api.py                  # dev server with auto-reload on port 8001
    uvicorn api:app --port 8001    # production-style

Notes
-----
* Django is NOT initialised — utility modules are imported directly.
  All Django-bound imports (run_bias_agent, compute_match_score) are
  intentionally avoided; we call the pure-logic helpers instead.
* resume_parser needs a real file path, so /parse-resume accepts
  base64-encoded file bytes and writes a temp file that is always
  cleaned up in a finally block.
"""

from __future__ import annotations

import base64
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ── sys.path: make "recruitment" package importable from project root ──────────
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Utility imports (all Django-free at module load time) ──────────────────────
from recruitment.utils.resume_parser import parse_resume                     # noqa: E402
from recruitment.utils.match_scorer import (                                  # noqa: E402
    score_skills_overlap,
    score_text_similarity,
    analyze_skill_gap,
)
# Import only the dispatch table — run_bias_agent() is intentionally skipped
# because it performs a lazy `from recruitment.models import …` (Django ORM).
from recruitment.utils.bias_agent import _EVALUATORS                         # noqa: E402
from recruitment.utils.bias_detector import scan_job_description             # noqa: E402


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FairHire AI Utilities API",
    description=(
        "REST wrapper around FairHire's four pure-Python utility modules: "
        "resume parsing, candidate–job match scoring, "
        "bias-criteria evaluation, and job-description bias detection."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ══════════════════════════════════════════════════════════════════════════════
# 1.  POST /parse-resume
# ══════════════════════════════════════════════════════════════════════════════

class ParseResumeRequest(BaseModel):
    """Base64-encoded resume file.  Accepts PDF, DOCX, or DOC."""

    filename: str = Field(
        ...,
        description="Original file name including extension, e.g. 'resume.pdf'."
        " Used solely to determine the file type (.pdf / .docx / .doc).",
        examples=["john_doe_resume.pdf"],
    )
    content_base64: str = Field(
        ...,
        description="Raw file bytes encoded as standard base64 (RFC 4648).",
        examples=["JVBERi0xLjQKJ..."],
    )


class ParseResumeResponse(BaseModel):
    """Structured data extracted from the resume."""

    skills: list[str] = Field(
        description="Detected skill keywords, title-cased (e.g. 'Python', 'Machine Learning')."
    )
    experience_years: Optional[int] = Field(
        description="Largest number of years of experience found, or null if none detected."
    )
    education: str = Field(
        description="First degree-containing line from the resume, or empty string."
    )
    raw_text: str = Field(
        description="Full extracted plain text of the resume (useful as input to /score-match)."
    )


_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}


@app.post(
    "/parse-resume",
    response_model=ParseResumeResponse,
    summary="Parse a PDF or DOCX resume",
    tags=["Resume"],
)
def parse_resume_endpoint(body: ParseResumeRequest) -> ParseResumeResponse:
    """
    Decode the base64 file, write it to a temporary file, run the resume
    parser, then delete the temp file.

    The parser uses **PyMuPDF** for PDFs and **python-docx** for Word files.
    It detects 100+ technical and soft-skill keywords, infers years of
    experience via regex, and extracts the first degree-containing line.
    """
    # ── 1. Decode base64 ───────────────────────────────────────────────────────
    try:
        file_bytes = base64.b64decode(body.content_base64, validate=True)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="content_base64 is not valid base64. "
                   "Encode the raw file bytes with base64.b64encode().",
        )

    # ── 2. Validate extension ──────────────────────────────────────────────────
    suffix = Path(body.filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}'. "
                   f"Supported: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    # ── 3. Write temp file, parse, always clean up ────────────────────────────
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)

        result = parse_resume(str(tmp_path))

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Resume parsing failed: {exc}",
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    return ParseResumeResponse(
        skills=result["skills"],
        experience_years=result["experience_years"],
        education=result["education"],
        raw_text=result["raw_text"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2.  POST /score-match
# ══════════════════════════════════════════════════════════════════════════════

class ScoreMatchRequest(BaseModel):
    """Inputs required to compute a candidate–job fit score."""

    candidate_skills: list[str] = Field(
        ...,
        description="Skills possessed by the candidate "
                    "(combine profile skills and parsed-resume skills for best accuracy).",
        examples=[["Python", "Django", "SQL", "Docker"]],
    )
    required_skills: list[str] = Field(
        ...,
        description="Skills required by the job posting (comma-split list from JobPosting.required_skills).",
        examples=[["Python", "React", "SQL", "AWS"]],
    )
    candidate_text: str = Field(
        default="",
        description="Full resume raw text (from /parse-resume) or bio+skills+education fallback. "
                    "Used for TF-IDF text similarity. Empty string disables that component.",
    )
    job_text: str = Field(
        default="",
        description="Job title + description + required_skills concatenated. "
                    "Used for TF-IDF text similarity. Empty string disables that component.",
    )


class ScoreMatchResponse(BaseModel):
    """Composite fit score and its constituent components."""

    composite_score: int = Field(
        description="Weighted fit score 0–100. Formula: skill_overlap×0.70 + text_similarity×0.30."
    )
    skill_overlap_pct: float = Field(
        description="Percentage of required skills the candidate possesses (0–100)."
    )
    text_similarity_pct: float = Field(
        description="TF-IDF cosine similarity between candidate text and job text (0–100)."
    )
    skill_gap: list[str] = Field(
        description="Required skills the candidate is missing (case-insensitive comparison)."
    )
    score_label: str = Field(
        description="Human-readable strength label: 'Strong' (≥70), 'Moderate' (40–69), 'Weak' (<40)."
    )


@app.post(
    "/score-match",
    response_model=ScoreMatchResponse,
    summary="Compute a candidate–job fit score",
    tags=["Scoring"],
)
def score_match_endpoint(body: ScoreMatchRequest) -> ScoreMatchResponse:
    """
    Computes a composite 0–100 fit score using the same weighting as
    FairHire's Django application layer:

    * **Skill overlap (70%)** — fraction of required skills present in the
      candidate's skill list; purely set-based, case-insensitive.
    * **Text similarity (30%)** — TF-IDF cosine similarity between the
      candidate's resume text and the job description; falls back to 0.0
      if either text is empty.

    Also returns the skill gap (missing required skills) so callers can
    surface improvement suggestions to the candidate.
    """
    skill_pct   = score_skills_overlap(body.candidate_skills, body.required_skills)
    text_pct    = score_text_similarity(body.candidate_text, body.job_text)
    composite   = min(100, max(0, round(skill_pct * 0.70 + text_pct * 0.30)))
    gap         = analyze_skill_gap(body.candidate_skills, body.required_skills)

    if composite >= 70:
        label = "Strong"
    elif composite >= 40:
        label = "Moderate"
    else:
        label = "Weak"

    return ScoreMatchResponse(
        composite_score=composite,
        skill_overlap_pct=skill_pct,
        text_similarity_pct=text_pct,
        skill_gap=gap,
        score_label=label,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 3.  POST /evaluate-bias
# ══════════════════════════════════════════════════════════════════════════════

class CandidateData(BaseModel):
    """
    Flat representation of a candidate's profile, mirroring the fields
    read by the bias-agent evaluators.

    Parsed-resume fields (parsed_education, parsed_experience_years,
    raw_text) are optional — they are used as fallback sources by the
    experience and college-tier evaluators.  Supply them when available
    from a prior /parse-resume call for best accuracy.
    """

    experience_years: int = Field(
        default=0,
        ge=0,
        description="Years of experience from the candidate's profile.",
    )
    education: str = Field(
        default="",
        description="Manually entered education string, e.g. 'B.Tech CSE, IIT Delhi'.",
    )
    gender: str = Field(
        default="",
        description="Candidate's stated gender (optional). Used only by the 'gender' criterion.",
        examples=["Male", "Female", "Non-binary", "Prefer not to say", ""],
    )
    bio: str = Field(default="", description="Candidate's profile bio / summary.")
    skills: str = Field(
        default="",
        description="Comma-separated skills string from the candidate's profile, "
                    "e.g. 'Python, Django, SQL'.",
    )
    # ── Optional parsed-resume enrichment ─────────────────────────────────────
    parsed_education: str = Field(
        default="",
        description="Education line extracted by /parse-resume (parsed_education field).",
    )
    parsed_experience_years: Optional[int] = Field(
        default=None,
        description="Experience years extracted by /parse-resume. "
                    "Takes precedence over experience_years when higher.",
    )
    raw_text: str = Field(
        default="",
        description="Full resume text from /parse-resume (raw_text field). "
                    "Searched by the college-tier and custom evaluators.",
    )


class CriterionInput(BaseModel):
    """A single HR hiring criterion to evaluate the candidate against."""

    criterion: str = Field(
        ...,
        description=(
            "Criterion type. One of:\n"
            "- `experience_min` — minimum/range years of experience\n"
            "- `college_tier`   — Tier 1 or Tier 2 Indian institution\n"
            "- `gender`         — gender preference (legally sensitive)\n"
            "- `custom`         — keyword/phrase search across the profile"
        ),
        examples=["experience_min", "college_tier", "gender", "custom"],
    )
    value: str = Field(
        ...,
        description=(
            "Criterion value whose format depends on the type:\n"
            "- `experience_min`: `'3'`, `'5+'`, or `'2-4'` (years)\n"
            "- `college_tier`:   `'Tier 1'` or `'Tier 2'`\n"
            "- `gender`:         `'Male'`, `'Female'`, `'any'`, etc.\n"
            "- `custom`:         any keyword or phrase, e.g. `'open source'`"
        ),
        examples=["3+", "Tier 1", "Female", "open source"],
    )


class CriterionResult(BaseModel):
    """Evaluation result for a single criterion."""

    criterion: str
    value: str
    passed: bool = Field(description="True if the candidate satisfies this criterion.")
    detail: str  = Field(description="Human-readable explanation of the pass/fail decision.")


class EvaluateBiasRequest(BaseModel):
    candidate: CandidateData
    criteria: Annotated[list[CriterionInput], Field(min_length=1)] = Field(
        ...,
        description="One or more criteria to evaluate. At least one is required.",
    )


class EvaluateBiasResponse(BaseModel):
    results: list[CriterionResult]
    passed_count: int = Field(description="Number of criteria the candidate passed.")
    failed_count: int = Field(description="Number of criteria the candidate failed.")


_VALID_CRITERIA = frozenset(_EVALUATORS)


def _build_profile(data: CandidateData) -> SimpleNamespace:
    """
    Construct a SimpleNamespace that satisfies the attribute interface
    expected by all four evaluators in bias_agent.py.

    The evaluators access `profile.parse_result.*` inside try/except blocks,
    so providing a nested SimpleNamespace (rather than None) is sufficient
    even when no parsed data is available.
    """
    parse_result = SimpleNamespace(
        parsed_education=data.parsed_education,
        parsed_experience_years=data.parsed_experience_years,
        raw_text=data.raw_text,
    )
    return SimpleNamespace(
        experience_years=data.experience_years,
        education=data.education,
        gender=data.gender,
        bio=data.bio,
        skills=data.skills,
        parse_result=parse_result,
    )


@app.post(
    "/evaluate-bias",
    response_model=EvaluateBiasResponse,
    summary="Evaluate a candidate against HR bias criteria",
    tags=["Bias"],
)
def evaluate_bias_endpoint(body: EvaluateBiasRequest) -> EvaluateBiasResponse:
    """
    Runs the Bias Agent's individual evaluators against each supplied
    criterion.  Results mirror what FairHire stores as `ApplicationBiasResult`
    records, but without touching the database.

    **Criterion types and their logic:**

    | Type | Value format | Logic |
    |---|---|---|
    | `experience_min` | `'5'`, `'5+'`, `'2-4'` | Compares candidate's experience years; parsed_experience_years wins if higher |
    | `college_tier` | `'Tier 1'`, `'Tier 2'` | Keyword search in education + raw_text against a curated list of Indian institutions |
    | `gender` | `'Male'`, `'Female'`, `'any'`, … | Exact case-insensitive match against candidate's stated gender |
    | `custom` | any phrase | Substring search across bio, skills, education, gender, and raw_text |

    Unknown criterion types are rejected with **422**.
    Evaluator exceptions are caught and returned as failed results.
    """
    # Validate all criterion types up front for a clean error message
    unknown = [c.criterion for c in body.criteria if c.criterion not in _VALID_CRITERIA]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown criterion type(s): {unknown}. "
                   f"Valid values: {sorted(_VALID_CRITERIA)}",
        )

    profile = _build_profile(body.candidate)
    results: list[CriterionResult] = []

    for crit in body.criteria:
        evaluator = _EVALUATORS[crit.criterion]
        try:
            passed, detail = evaluator(profile, crit.value)
        except Exception as exc:  # evaluator is best-effort; never propagate
            passed = False
            detail = f"Evaluation error: {exc}"

        results.append(CriterionResult(
            criterion=crit.criterion,
            value=crit.value,
            passed=passed,
            detail=detail,
        ))

    passed_count = sum(1 for r in results if r.passed)
    return EvaluateBiasResponse(
        results=results,
        passed_count=passed_count,
        failed_count=len(results) - passed_count,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4.  POST /detect-bias
# ══════════════════════════════════════════════════════════════════════════════

class DetectBiasRequest(BaseModel):
    """Job description text to scan."""

    text: str = Field(
        ...,
        description="The full job description text to scan for biased language.",
        examples=["We need a rockstar ninja developer who can dominate the market."],
    )


class DetectBiasResponse(BaseModel):
    """Bias scan results."""

    warnings: list[str] = Field(
        description=(
            "One warning string per bias category that triggered. "
            "Each entry names the detected term(s) and suggests neutral alternatives. "
            "Empty list means no bias was detected."
        )
    )
    is_clean: bool = Field(
        description="True if no biased language was detected (warnings is empty)."
    )
    warning_count: int = Field(
        description="Total number of bias categories triggered."
    )


@app.post(
    "/detect-bias",
    response_model=DetectBiasResponse,
    summary="Scan a job description for biased language",
    tags=["Bias"],
)
def detect_bias_endpoint(body: DetectBiasRequest) -> DetectBiasResponse:
    """
    Scans the job description text against four lexicon categories using
    whole-word regex matching (word boundaries prevent false positives
    like matching `'stand'` inside `'standard'`):

    | Category | Example terms |
    |---|---|
    | `gendered_masculine` | ninja, rockstar, dominate, aggressive, guru |
    | `gendered_feminine` | nurturing, empathetic, compassionate |
    | `ageist` | digital native, young, recent grad, mature |
    | `exclusionary_ableist` | normal, healthy, able-bodied, crazy |

    Each triggered category produces one warning string that names the
    matched term(s) and recommends neutral alternatives.  Empty text
    returns zero warnings without error.
    """
    warnings = scan_job_description(body.text)
    return DetectBiasResponse(
        warnings=warnings,
        is_clean=len(warnings) == 0,
        warning_count=len(warnings),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,          # auto-reload on file changes (dev convenience)
        reload_dirs=[str(_ROOT)],
    )
