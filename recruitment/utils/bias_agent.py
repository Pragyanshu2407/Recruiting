"""
bias_agent.py
-------------
Evaluates job applicants against HR-defined bias/hiring-preference criteria.

Each criterion type has a dedicated evaluator that returns (passed: bool, detail: str).
`run_bias_agent(application)` orchestrates all evaluations and persists results.

Sensitivity levels are stored on the criteria model and exposed here for reference:
  - experience_min  → low    (objective threshold)
  - college_tier    → medium (exclusionary but common)
  - gender          → high   (legally sensitive in many jurisdictions)
  - custom          → medium (depends on content)
"""
from __future__ import annotations


# ── Tier keyword maps ─────────────────────────────────────────────────────────

_TIER1_KEYWORDS = [
    "iit", "iim", "isc", "bits pilani", "nit trichy", "nit surathkal",
    "nit warangal", "nit calicut", "iisc", "iiit hyderabad", "dtu", "nsit",
    "anna university", "vit", "srm",  # extended Tier 1 for broader coverage
]
_TIER2_KEYWORDS = [
    "nit", "iiit", "bits", "thapar", "pec", "coep", "sjce", "mnnit",
    "mnit", "nitrr", "nitk", "nitw", "nitc", "nita",
]


def _education_text(profile) -> str:
    """Return all available education text from a candidate profile."""
    sources = [profile.education or ""]
    try:
        sources.append(profile.parse_result.parsed_education or "")
        sources.append(profile.parse_result.raw_text or "")
    except Exception:
        pass
    return " ".join(sources).lower()


# ── Individual evaluators ─────────────────────────────────────────────────────

def evaluate_experience(profile, value: str) -> tuple[bool, str]:
    """Check if the candidate meets the minimum experience requirement."""
    try:
        required = int(value)
    except (ValueError, TypeError):
        return True, "Invalid criterion value — skipped"

    actual = profile.experience_years or 0
    # Also check parsed result as a fallback
    try:
        parsed = profile.parse_result.parsed_experience_years
        if parsed and parsed > actual:
            actual = parsed
    except Exception:
        pass

    if actual >= required:
        return True, f"{actual} yr(s) ≥ required {required} yr(s)"
    return False, f"Only {actual} yr(s) — requires {required}+ yr(s)"


def evaluate_college_tier(profile, value: str) -> tuple[bool, str]:
    """Check if education text contains keywords matching the required tier."""
    edu = _education_text(profile)
    tier = value.lower().strip()

    if "tier 1" in tier or tier == "1":
        for kw in _TIER1_KEYWORDS:
            if kw in edu:
                return True, f"Detected '{kw}' → qualifies as Tier 1"
        return False, "No Tier 1 institution detected in education"

    elif "tier 2" in tier or tier == "2":
        for kw in _TIER1_KEYWORDS + _TIER2_KEYWORDS:
            if kw in edu:
                return True, f"Detected '{kw}' → qualifies as Tier 1/2"
        return False, "No Tier 1 or Tier 2 institution detected"

    return True, f"Unrecognised tier value '{value}' — skipped"


def evaluate_gender(profile, value: str) -> tuple[bool, str]:
    """Check if the candidate's stated gender matches the preference."""
    preferred = value.strip().lower()
    if preferred in ("any", "all", ""):
        return True, "No gender restriction"

    actual = (profile.gender or "").strip().lower()
    if not actual:
        return False, "Candidate has not specified their gender"

    if actual == preferred:
        return True, f"Gender matches preference ({profile.gender})"
    return False, f"Gender '{profile.gender}' does not match preferred '{value}'"


def evaluate_custom(profile, value: str) -> tuple[bool, str]:
    """
    Search for the custom keyword/phrase in the candidate's resume text,
    bio, skills, or education. Returns True if found.
    """
    needle = value.strip().lower()
    if not needle:
        return True, "Empty custom rule — skipped"

    haystack_parts = [
        profile.bio or "",
        profile.skills or "",
        profile.education or "",
        profile.gender or "",
    ]
    try:
        haystack_parts.append(profile.parse_result.raw_text or "")
    except Exception:
        pass

    haystack = " ".join(haystack_parts).lower()
    if needle in haystack:
        return True, f"Found keyword '{value}' in candidate profile"
    return False, f"Keyword '{value}' not found in candidate profile"


# ── Dispatch table ─────────────────────────────────────────────────────────────

_EVALUATORS = {
    'experience_min': evaluate_experience,
    'college_tier':   evaluate_college_tier,
    'gender':         evaluate_gender,
    'custom':         evaluate_custom,
}


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_bias_agent(application) -> list:
    """
    Evaluate `application` against all `JobBiasCriteria` for its job.
    Creates/updates `ApplicationBiasResult` for each criterion.
    Returns a list of ApplicationBiasResult instances.

    This is best-effort — if evaluation fails for any criterion, that criterion
    is skipped rather than blocking the application.
    """
    # Lazy imports to avoid circular dependency at module load time
    from recruitment.models import ApplicationBiasResult

    job = application.job
    criteria = job.bias_criteria.all()

    results = []
    for criterion in criteria:
        try:
            profile = application.candidate.candidate_profile
            evaluator = _EVALUATORS.get(criterion.criterion, lambda p, v: (True, "Unknown criterion"))
            passed, detail = evaluator(profile, criterion.value)
        except Exception as exc:
            passed = False
            detail = f"Evaluation error: {exc}"

        result, _ = ApplicationBiasResult.objects.update_or_create(
            application=application,
            criterion=criterion,
            defaults={'passed': passed, 'detail': detail},
        )
        results.append(result)

    return results
