from app.services.matching.skill_gap import compute_skill_gap


def test_full_overlap():
    result = compute_skill_gap(["Python", "Django"], [], ["Python", "Django"])
    assert result["overlap_ratio"] == 1.0
    assert result["missing_skills"] == []


def test_partial_overlap():
    result = compute_skill_gap(["Python"], [], ["Python", "Kubernetes"])
    assert result["overlap_ratio"] == 0.5
    assert result["missing_skills"] == ["Kubernetes"]


def test_inferred_skills_count_as_known():
    result = compute_skill_gap([], ["Docker"], ["Docker"])
    assert result["overlap_ratio"] == 1.0


def test_canonicalization_bridges_variants():
    # "postgres" and "postgresql" both canonicalize to PostgreSQL
    result = compute_skill_gap(["postgres"], [], ["postgresql"])
    assert result["overlap_ratio"] == 1.0


def test_no_requirements_means_full_score():
    result = compute_skill_gap(["Python"], [], [])
    assert result["overlap_ratio"] == 1.0
