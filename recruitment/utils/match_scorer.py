"""
match_scorer.py
---------------
Compute a 0-100 fit score between a job application and its associated job.

Scoring breakdown:
  - Skill overlap  (70% weight): Jaccard-like metric against job's required skills
  - Text similarity (30% weight): TF-IDF cosine similarity between candidate's
    resume raw text and the job description + required skills text.

No external API calls — fully self-contained.
"""
from __future__ import annotations
import re


# ---------------------------------------------------------------------------
# Skill overlap
# ---------------------------------------------------------------------------

def _normalise(skill: str) -> str:
    """Lower-case and strip whitespace for fuzzy comparison."""
    return skill.strip().lower()


def score_skills_overlap(candidate_skills: list[str], required_skills: list[str]) -> float:
    """
    Return a 0-100 score reflecting how many of the *required* skills
    appear in the candidate's skill list.

    Formula: (matched / total_required) * 100
    Returns 0.0 if required_skills is empty.
    """
    if not required_skills:
        return 0.0

    required_norm = {_normalise(s) for s in required_skills}
    candidate_norm = {_normalise(s) for s in candidate_skills}

    matched = len(required_norm & candidate_norm)
    return round((matched / len(required_norm)) * 100, 1)


# ---------------------------------------------------------------------------
# Text similarity (TF-IDF cosine)
# ---------------------------------------------------------------------------

def score_text_similarity(candidate_text: str, job_text: str) -> float:
    """
    Return a 0-100 cosine similarity score between two text blobs using
    a simple TF-IDF vectoriser.

    Returns 0.0 if either text is empty.
    """
    if not candidate_text or not job_text:
        return 0.0

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        tfidf = vectorizer.fit_transform([candidate_text, job_text])
        score = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return round(float(score) * 100, 1)

    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------

def compute_match_score(application) -> int:
    """
    Given a JobApplication ORM instance (with related job and candidate),
    compute and return a composite 0-100 integer fit score.

    Weights:
      - Skill overlap  → 70%
      - Text similarity → 30%

    Falls back gracefully if profile / parse result data is missing.
    """
    job = application.job
    candidate_user = application.candidate

    # --- required skills from job ---
    required_skills = job.required_skills_list()

    # --- candidate skills: parsed + manual, deduplicated ---
    candidate_skills: list[str] = []

    try:
        profile = candidate_user.candidate_profile
        candidate_skills.extend(profile.skills_list())
    except Exception:
        pass

    try:
        parse_result = candidate_user.candidate_profile.parse_result
        candidate_skills.extend(parse_result.parsed_skills_list())
    except Exception:
        pass

    # Deduplicate (case-insensitive)
    seen: set[str] = set()
    deduped: list[str] = []
    for s in candidate_skills:
        if s.lower() not in seen:
            seen.add(s.lower())
            deduped.append(s)
    candidate_skills = deduped

    # --- raw text for similarity ---
    candidate_text = ""
    try:
        candidate_text = candidate_user.candidate_profile.parse_result.raw_text or ""
    except Exception:
        pass

    # Supplement candidate text with manually entered profile data if no raw text
    if not candidate_text:
        try:
            p = candidate_user.candidate_profile
            candidate_text = " ".join(filter(None, [p.bio, p.skills, p.education]))
        except Exception:
            pass

    job_text = f"{job.title} {job.description} {job.required_skills}"

    # --- compute components ---
    skill_score = score_skills_overlap(candidate_skills, required_skills)
    text_score = score_text_similarity(candidate_text, job_text)

    # Weighted blend
    composite = (skill_score * 0.70) + (text_score * 0.30)
    return min(100, max(0, round(composite)))
