import json
import re

from app.ai.llm import llm_router


SYSTEM_PROMPT = """You analyze a job description against a candidate's resume summary.
Extract ONLY skills/technologies explicitly required or clearly implied by the job description.
Also extract a broader list of ATS-relevant keywords: specific tools, certifications,
methodologies (e.g. "Agile", "Scrum"), and exact terms an Applicant Tracking System
would scan for verbatim — these can overlap with required_skills but should also include
softer/broader terms a resume keyword-matcher would look for.
Do not invent requirements that aren't stated or strongly implied.
Output ONLY valid JSON, no markdown, no commentary.
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def analyze_job_fit(
    resume_summary: str,
    job_title: str,
    job_description: str
) -> dict:
    """
    Single LLM call that does two things at once:
    1. Extracts the job's required skills from free-text description.
    2. Writes a short 1-2 sentence explanation of why this resume fits (or doesn't).

    Returns dict with:
    - required_skills
    - explanation

    Falls back safely if model output is malformed.
    """

    prompt = f"""Job title: {job_title}

Job description:
\"\"\"
{job_description[:3000]}
\"\"\"

Candidate resume summary:
\"\"\"
{resume_summary}
\"\"\"

Respond with ONLY this JSON shape:
{{
  "required_skills": ["string"],
  "ats_keywords": ["string"],
  "explanation": "1-2 sentence explanation of fit, mentioning specific overlaps or gaps"
}}
"""

    try:
        raw = llm_router.run(
            task="job_fit_analysis",
            system=SYSTEM_PROMPT,
            prompt=prompt,
        )

        raw = _strip_fences(raw)

        data = json.loads(raw)

        return {
            "required_skills": data.get("required_skills", []),
            "ats_keywords": data.get("ats_keywords", []),
            "explanation": data.get("explanation", ""),
        }

    except Exception:
        # One bad job should not break complete ranking
        return {
            "required_skills": [],
            "ats_keywords": [],
            "explanation": "Could not generate explanation."
            }