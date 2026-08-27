from app.linkedin.merge import merge_section_payloads


def test_merge_attaches_views_and_included() -> None:
    primary = {
        "data": {"elements": ["*urn:li:fsd_profile:1"]},
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                "entityUrn": "urn:li:fsd_profile:1",
                "firstName": "Ada",
            }
        ],
    }
    skills = {
        "elements": [{"name": "Python", "endorsementCount": 9}],
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Skill",
                "entityUrn": "urn:li:fsd_skill:py",
                "name": "Python",
                "endorsementCount": 9,
            }
        ],
    }

    merged = merge_section_payloads(primary, {"skillView": skills, "languageView": None})

    assert merged["skillView"]["elements"][0]["name"] == "Python"
    types = {item["$type"].rsplit(".", 1)[-1] for item in merged["included"]}
    assert "Profile" in types
    assert "Skill" in types
    assert "languageView" not in merged


def test_merge_does_not_overwrite_existing_view() -> None:
    primary = {"skillView": {"elements": [{"name": "Mathematics"}]}, "included": []}
    extra = {"elements": [{"name": "ShouldNotReplace"}]}
    merged = merge_section_payloads(primary, {"skillView": extra})
    assert merged["skillView"]["elements"][0]["name"] == "Mathematics"


def test_merge_reads_normalized_data_elements() -> None:
    primary = {"included": []}
    extra = {"data": {"elements": [{"name": "French", "proficiency": "NATIVE_OR_BILINGUAL"}]}}
    merged = merge_section_payloads(primary, {"languageView": extra})
    assert merged["languageView"]["elements"][0]["name"] == "French"
