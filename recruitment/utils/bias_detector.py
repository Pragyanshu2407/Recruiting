"""
bias_detector.py
----------------
Scans job descriptions for potentially exclusionary, biased, or highly-gendered language.
Returns a list of warnings that HR can review before publishing a job posting.
"""
from __future__ import annotations
import re

# Simple lexicons for demonstration purposes
BIAS_LEXICONS = {
    'gendered_masculine': {
        'terms': ['ninja', 'rockstar', 'assertive', 'dominate', 'aggressive', 'guru', 'hacker', 'crush it', 'kill it'],
        'warning': 'Strongly masculine-coded words can deter female applicants. Try: "expert", "specialist", "driven", or "succeed".'
    },
    'gendered_feminine': {
        'terms': ['nurturing', 'supportive', 'empathetic', 'compassionate', 'sensitive'],
        'warning': 'Feminine-coded words can sometimes reinforce stereotypical role expectations. Try to balance these with neutral action-oriented words.'
    },
    'ageist': {
        'terms': ['digital native', 'young', 'energetic', 'recent grad', 'mature', 'seasoned', 'old school'],
        'warning': 'Age-related terminology can trigger age-discrimination concerns. Focus on experience level or specific skills instead of age.'
    },
    'exclusionary_ableist': {
        'terms': ['normal', 'healthy', 'stand', 'walk', 'able-bodied', 'crazy', 'insane', 'blind to'],
        'warning': 'Ableist language can be exclusionary. Ensure physical requirements (like standing/walking) are truly essential to the job duties.'
    }
}


def scan_job_description(text: str) -> list[str]:
    """
    Scans the provided text against bias lexicons.
    Returns a list of formatted warning strings.
    """
    if not text:
        return []

    text_lower = text.lower()
    warnings = []

    for category, data in BIAS_LEXICONS.items():
        found_terms = []
        for term in data['terms']:
            # Use regex word boundaries to avoid matching substrings like "stand" in "standard"
            if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
                found_terms.append(term)
        
        if found_terms:
            terms_str = ", ".join(f"'{t}'" for t in found_terms)
            warnings.append(f"Found potentially biased terms ({terms_str}): {data['warning']}")

    return warnings
