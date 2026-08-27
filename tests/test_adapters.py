from pathlib import Path

import pytest

from app.adapters import get_adapter, list_adapters
from app.adapters.default import DefaultProfileAdapter
from app.adapters.json_mapper import apply_mapping, load_mapping
from app.adapters.profilelens import ProfileLensAdapter
from app.exceptions import LinkedInError
from app.schemas import Experience, Language, ProfileResponse, Skill


def _sample_profile() -> ProfileResponse:
    return ProfileResponse(
        publicId="ada-lovelace",
        profileUrl="https://www.linkedin.com/in/ada-lovelace/",
        fullName="Ada Lovelace",
        firstName="Ada",
        lastName="Lovelace",
        headline="Mathematician",
        location="London",
        about="Notes",
        experience=[
            Experience(title="Analyst", company="Analytical Engine Co."),
            Experience(title="Writer", company="Royal Society"),
        ],
        skills=[Skill(name="Mathematics", endorsementCount=42)],
        languages=[Language(name="English", proficiency="Native or bilingual")],
    )


def test_registry_lists_both_adapters() -> None:
    names = {a.name for a in list_adapters()}
    assert names == {"default", "profilelens"}


def test_default_adapter_preserves_nested_shape() -> None:
    data = DefaultProfileAdapter().adapt(_sample_profile())
    assert data["fullName"] == "Ada Lovelace"
    assert data["experience"][0]["company"] == "Analytical Engine Co."
    assert data["skills"][0]["name"] == "Mathematics"


def test_profilelens_adapter_flattens() -> None:
    data = ProfileLensAdapter().adapt(_sample_profile())
    assert data["companyName"] == "Analytical Engine Co."
    assert data["jobTitle"] == "Analyst"
    assert data["previousCompanyName"] == "Royal Society"
    assert data["linkedinSkillsLabel"] == "Mathematics"
    assert data["languagesLabel"] == "English (Native or bilingual)"
    assert len(data["experienceJson"]) == 2


def test_profilelens_mapping_json_is_valid() -> None:
    doc = load_mapping("profilelens")
    assert doc.version == 1
    keys = [field.to for field in doc.fields]
    assert len(keys) == len(set(keys))
    assert "companyName" in keys
    assert "experienceJson" in keys
    path = Path(__file__).resolve().parents[1] / "backend/app/adapters/mappings/profilelens.json"
    assert path.is_file()


def test_mapping_engine_uses_context_where_clause() -> None:
    doc = load_mapping("profilelens")
    root = {
        "firstName": "Ada",
        "experience": [
            {"title": "Past", "company": "A", "dateRange": {"current": False}},
            {"title": "Now", "company": "B", "dateRange": {"current": True}},
        ],
        "education": [],
        "skills": [],
        "languages": [],
        "certifications": [],
        "honors": [],
        "volunteer": [],
    }
    data = apply_mapping(doc, root)
    assert data["jobTitle"] == "Now"
    assert data["companyName"] == "B"
    assert data["previousCompanyName"] == "A"


def test_get_adapter_unknown() -> None:
    with pytest.raises(LinkedInError) as exc:
        get_adapter("missing")
    assert exc.value.code == "invalid_adapter"
