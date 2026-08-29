from pathlib import Path

import pytest

from pydantic import ValidationError

from app.adapters import get_adapter, list_adapters
from app.adapters.catalog import adapter_schema_presets
from app.adapters.custom import CustomProfileAdapter
from app.adapters.json_mapper import apply_mapping, list_mapping_names, load_mapping
from app.adapters.mapping_schema import MappingDocument
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


def test_registry_lists_profilelens_and_custom() -> None:
    names = {a.name for a in list_adapters()}
    assert names == {"profilelens", "custom"}
    assert list_mapping_names() == ["profilelens"]
    presets = adapter_schema_presets()
    assert list(presets) == ["profilelens"]
    assert presets["profilelens"]["context"]["currentJob"]["from"] == "experience"


def test_profilelens_is_the_default_adapter() -> None:
    data = get_adapter(None).adapt(_sample_profile())
    assert data["fullName"] == "Ada Lovelace"
    assert data["companyName"] == "Analytical Engine Co."
    assert data["jobTitle"] == "Analyst"
    assert data["linkedinSkillsLabel"] == "Mathematics"


def test_profilelens_adapter_flattens() -> None:
    data = get_adapter("profilelens").adapt(_sample_profile())
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
    with pytest.raises(LinkedInError) as exc:
        get_adapter("default")
    assert exc.value.code == "invalid_adapter"


def test_custom_adapter_requires_mapping() -> None:
    with pytest.raises(LinkedInError) as exc:
        get_adapter("custom")
    assert exc.value.code == "invalid_schema"


def test_custom_adapter_projects_named_keys() -> None:
    doc = MappingDocument.model_validate(
        {
            "fields": [
                {"to": "name", "from": "fullName"},
                {"to": "title", "from": "experience.0.title"},
                {"to": "company", "from": "experience.0.company"},
            ]
        }
    )
    data = CustomProfileAdapter(doc).adapt(_sample_profile())
    assert data == {
        "name": "Ada Lovelace",
        "title": "Analyst",
        "company": "Analytical Engine Co.",
    }


def test_mapping_nested_to_paths() -> None:
    doc = MappingDocument.model_validate(
        {
            "fields": [
                {"to": "identity.name", "from": "fullName"},
                {"to": "identity.headline", "from": "headline"},
                {"to": "work", "from": "experience"},
            ]
        }
    )
    data = apply_mapping(doc, _sample_profile().model_dump(mode="json"))
    assert data["identity"] == {"name": "Ada Lovelace", "headline": "Mathematician"}
    assert data["work"][0]["company"] == "Analytical Engine Co."


def test_mapping_rejects_nested_prefix_conflict() -> None:
    with pytest.raises(ValidationError):
        MappingDocument.model_validate(
            {
                "fields": [
                    {"to": "identity", "from": "fullName"},
                    {"to": "identity.name", "from": "firstName"},
                ]
            }
        )


def test_mapping_rejects_duplicate_output_keys() -> None:
    with pytest.raises(ValidationError):
        MappingDocument.model_validate(
            {"fields": [{"to": "name", "from": "fullName"}, {"to": "name", "from": "headline"}]}
        )
