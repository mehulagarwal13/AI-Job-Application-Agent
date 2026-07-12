from app.services.job_sources.experience_extractor import extract_min_years_required

def normalize_adzuna_job(raw: dict) -> dict:
    description = raw.get("description", "").strip()
    return {
        "job_id": f"adzuna_{raw.get('id')}",
        "title": raw.get("title", "").strip(),
        "company": (raw.get("company") or {}).get("display_name"),
        "location": (raw.get("location") or {}).get("display_name"),
        "description": description,
        "salary_min": float(raw["salary_min"]) if raw.get("salary_min") else None,
        "salary_max": float(raw["salary_max"]) if raw.get("salary_max") else None,
        "remote": None,  # Adzuna doesn't expose a reliable remote flag
        "min_years_required": extract_min_years_required(description),
        "apply_url": raw.get("redirect_url"),
        "source": "adzuna",
    }