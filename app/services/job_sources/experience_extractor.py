import re

# Ordered by specificity — first match wins
PATTERNS = [
    r"(\d+)\s*\+?\s*-\s*\d+\s*years?",       # "3-5 years", "3 - 5 years"
    r"(\d+)\s*\+\s*years?",                   # "5+ years"
    r"minimum\s+(?:of\s+)?(\d+)\s*years?",    # "minimum of 3 years"
    r"at least\s+(\d+)\s*years?",             # "at least 4 years"
    r"(\d+)\s*years?\s+of\s+experience",      # "5 years of experience"
]


def extract_min_years_required(description: str) -> int | None:
    """
    Heuristic regex extraction of minimum years of experience from a job
    description. Returns None if no pattern matches — this does NOT mean
    the job has no requirement, just that we couldn't confidently detect
    one from wording. None is treated as 'unknown', not 'zero', downstream.
    """
    if not description:
        return None

    text = description.lower()
    for pattern in PATTERNS:
        match = re.search(pattern, text)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue
    return None