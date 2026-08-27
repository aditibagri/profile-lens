from app.linkedin.merge import merge_section_payloads
from app.linkedin.parser import parse_profile


def test_parse_dash_profile(dash_payload: dict) -> None:
    profile = parse_profile(
        dash_payload,
        "ada-lovelace",
        "https://www.linkedin.com/in/ada-lovelace/",
    )

    assert profile.fullName == "Ada Lovelace"
    assert profile.firstName == "Ada"
    assert profile.lastName == "Lovelace"
    assert profile.headline.startswith("Mathematician")
    assert profile.location == "London, England"
    assert "algorithm" in (profile.about or "")
    assert profile.pronouns == "she/her"
    assert profile.profileImage.endswith("large.jpg")
    assert profile.backgroundImage.endswith("cover.jpg")

    assert len(profile.experience) == 1
    assert profile.experience[0].title == "Analyst"
    assert profile.experience[0].company == "Analytical Engine Co."
    assert profile.experience[0].dateRange is not None
    assert profile.experience[0].dateRange.start == "1842-01"
    assert profile.experience[0].dateRange.end == "1852-06"

    assert profile.education[0].school == "Home education"
    assert profile.education[0].degree == "Mathematics"

    skill_names = {s.name for s in profile.skills}
    assert skill_names == {"Mathematics", "Algorithms"}
    math = next(s for s in profile.skills if s.name == "Mathematics")
    assert math.endorsementCount == 42

    assert profile.certifications[0].name == "Analytical Engine Notes"
    assert profile.certifications[0].issuer == "Royal Society"
    assert profile.certifications[0].issuedOn == "1843-07"

    assert profile.languages[0].name == "English"
    assert profile.languages[0].proficiency == "Native or bilingual"

    assert profile.volunteer[0].organization == "Science Museum"
    assert profile.honors[0].title == "Countess of Lovelace"


def test_parse_legacy_profile_view(profile_view_payload: dict) -> None:
    profile = parse_profile(
        profile_view_payload,
        "grace-hopper",
        "https://www.linkedin.com/in/grace-hopper/",
    )

    assert profile.fullName == "Grace Hopper"
    assert profile.publicId == "grace-hopper"
    assert profile.location == "Arlington, Virginia"
    assert profile.profileImage.endswith("photo.jpg")
    assert profile.experience[0].company == "United States Navy"
    assert profile.education[0].school == "Yale University"
    assert profile.skills[0].name == "COBOL"
    assert profile.certifications[0].issuer == "US Navy"
    assert profile.languages[0].proficiency == "Native or bilingual"
    assert profile.volunteer[0].role == "Speaker"
    assert profile.honors[0].title == "Presidential Medal of Freedom"


def test_parse_fills_thin_dash_from_section_views() -> None:
    thin = {
        "data": {"elements": ["*urn:li:fsd_profile:ABC123"]},
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                "entityUrn": "urn:li:fsd_profile:ABC123",
                "publicIdentifier": "ada-lovelace",
                "firstName": "Ada",
                "lastName": "Lovelace",
                "headline": "Mathematician",
            }
        ],
    }
    merged = merge_section_payloads(
        thin,
        {
            "skillView": {"elements": [{"name": "Mathematics", "endorsementCount": 42}]},
            "skillCategoryView": {
                "elements": [
                    {
                        "name": "Industry Knowledge",
                        "endorsedSkills": [
                            {"skill": {"name": "Algorithms"}, "endorsementCount": 7},
                            {"name": "Mathematics", "endorsementCount": 1},
                        ],
                    }
                ]
            },
            "certificationView": {
                "elements": [{"name": "Analytical Engine Notes", "authority": "Royal Society"}]
            },
            "languageView": {
                "elements": [{"name": "English", "proficiency": "NATIVE_OR_BILINGUAL"}]
            },
        },
    )

    profile = parse_profile(
        merged,
        "ada-lovelace",
        "https://www.linkedin.com/in/ada-lovelace/",
    )
    assert profile.fullName == "Ada Lovelace"
    assert {s.name for s in profile.skills} == {"Mathematics", "Algorithms"}
    math = next(s for s in profile.skills if s.name == "Mathematics")
    assert math.endorsementCount == 42
    assert profile.certifications[0].issuer == "Royal Society"
    assert profile.languages[0].proficiency == "Native or bilingual"
