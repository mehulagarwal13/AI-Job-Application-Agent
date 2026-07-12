from app.models.db_models import JobRecord
from app.services.matching.hard_filters import apply_hard_filters


def _job(**kwargs) -> JobRecord:
    defaults = {"job_id": "j1", "title": "Backend Engineer", "location": "London",
                "salary_min": None, "min_years_required": None}
    defaults.update(kwargs)
    return JobRecord(**defaults)


def test_location_filter():
    jobs = [(_job(location="London"), 0.9), (_job(job_id="j2", location="Berlin"), 0.8)]
    result = apply_hard_filters(jobs, location_contains="london")
    assert len(result) == 1
    assert result[0][0].location == "London"


def test_salary_filter():
    jobs = [(_job(salary_min=30000.0), 0.9), (_job(job_id="j2", salary_min=80000.0), 0.8)]
    result = apply_hard_filters(jobs, min_salary=50000)
    assert len(result) == 1
    assert result[0][0].salary_min == 80000.0


def test_experience_filter_with_buffer():
    # Candidate has 4y; job wants 5y -> passes with the 1y buffer; job wanting 7y -> excluded
    jobs = [(_job(min_years_required=5.0), 0.9), (_job(job_id="j2", min_years_required=7.0), 0.8)]
    result = apply_hard_filters(jobs, candidate_years_experience=4.0)
    assert len(result) == 1
    assert result[0][0].min_years_required == 5.0


def test_unknown_fields_do_not_filter():
    jobs = [(_job(location=None, salary_min=None, min_years_required=None), 0.9)]
    # Location filter DOES require a location; salary/experience treat unknown as pass
    result = apply_hard_filters(jobs, min_salary=50000, candidate_years_experience=1.0)
    assert len(result) == 1
