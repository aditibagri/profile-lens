"""Canonical source fields visitors can map into a custom response schema."""

from __future__ import annotations

SCHEMA_FIELDS: list[dict[str, str]] = [
    {"path": "fullName", "label": "Full name", "group": "Identity"},
    {"path": "firstName", "label": "First name", "group": "Identity"},
    {"path": "lastName", "label": "Last name", "group": "Identity"},
    {"path": "headline", "label": "Headline", "group": "Identity"},
    {"path": "location", "label": "Location", "group": "Identity"},
    {"path": "about", "label": "About", "group": "Identity"},
    {"path": "pronouns", "label": "Pronouns", "group": "Identity"},
    {"path": "industry", "label": "Industry", "group": "Identity"},
    {"path": "publicId", "label": "Profile slug", "group": "Identity"},
    {"path": "profileUrl", "label": "Profile URL", "group": "Identity"},
    {"path": "profileImage", "label": "Profile photo URL", "group": "Identity"},
    {"path": "backgroundImage", "label": "Banner image URL", "group": "Identity"},
    {"path": "experience", "label": "Experience (full list)", "group": "History"},
    {"path": "education", "label": "Education (full list)", "group": "History"},
    {"path": "skills", "label": "Skills (full list)", "group": "History"},
    {"path": "certifications", "label": "Certifications (full list)", "group": "History"},
    {"path": "languages", "label": "Languages (full list)", "group": "History"},
    {"path": "volunteer", "label": "Volunteer (full list)", "group": "History"},
    {"path": "honors", "label": "Honors (full list)", "group": "History"},
    {"path": "experience.0.title", "label": "Latest job title", "group": "Shortcuts"},
    {"path": "experience.0.company", "label": "Latest company", "group": "Shortcuts"},
    {"path": "experience.0.companyLogo", "label": "Latest company logo", "group": "Shortcuts"},
    {"path": "experience.0.location", "label": "Latest job location", "group": "Shortcuts"},
    {"path": "education.0.school", "label": "Latest school", "group": "Shortcuts"},
    {"path": "education.0.schoolLogo", "label": "Latest school logo", "group": "Shortcuts"},
    {"path": "education.0.degree", "label": "Latest degree", "group": "Shortcuts"},
    {"path": "education.0.fieldOfStudy", "label": "Latest field of study", "group": "Shortcuts"},
]


def adapter_schema_presets() -> dict[str, dict]:
    """Starting schemas the UI can show — loaded from ``mappings/*.json``."""
    from app.adapters.json_mapper import list_mapping_names, load_mapping

    presets: dict[str, dict] = {}
    for name in list_mapping_names():
        doc = load_mapping(name)
        presets[name] = {
            "description": doc.description,
            "fields": [
                {**field.model_dump(by_alias=True, exclude_none=True), "label": field.to}
                for field in doc.fields
            ],
            "context": {
                alias: selector.model_dump(by_alias=True, exclude_none=True)
                for alias, selector in doc.context.items()
            },
        }
    return presets
