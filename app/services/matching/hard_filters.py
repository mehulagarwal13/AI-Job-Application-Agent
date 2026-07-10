from app.models.db_models import JobRecord


def apply_hard_filters(
    scored_jobs: list[tuple[JobRecord, float]],
    location_contains: str | None = None,
    min_salary: int | None = None,
    candidate_years_experience: float | None = None,
    experience_buffer: float = 1.0,
) -> list[tuple[JobRecord, float]]:
    """
    experience_buffer allows some slack — job postings routinely say "5 years"
    as a soft preference, not a hard cutoff, and candidates with slightly less
    still regularly get interviews. A candidate is excluded only if their
    experience falls short by MORE than the buffer.
    """
    result = []
    for job, score in scored_jobs:
        if location_contains:
            if not job.location or location_contains.lower() not in job.location.lower():
                continue
        if min_salary:
            try:
                if job.salary_min and int(float(job.salary_min)) < min_salary:
                    continue
            except ValueError:
                pass

        if candidate_years_experience is not None and job.min_years_required:
            try:
                required = float(job.min_years_required)
                if candidate_years_experience < (required - experience_buffer):
                    continue
            except ValueError:
                pass  # unparseable — don't filter over bad data

        result.append((job, score))
    return result