import pytest

from app.exceptions import InvalidProfileUrlError
from app.linkedin.urls import extract_public_id


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.linkedin.com/in/williamhgates/", "williamhgates"),
        ("https://linkedin.com/in/williamhgates", "williamhgates"),
        ("www.linkedin.com/in/williamhgates?trk=foo", "williamhgates"),
        ("https://www.linkedin.com/in/ada-lovelace/", "ada-lovelace"),
        (
            "https://www.linkedin.com/in/williamhgates/overlay/about-this-profile/",
            "williamhgates",
        ),
    ],
)
def test_extract_public_id(url: str, expected: str) -> None:
    assert extract_public_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://example.com/in/someone",
        "https://www.linkedin.com/company/google",
        "https://www.linkedin.com/jobs/view/123",
        "https://www.linkedin.com/school/mit",
        "not a url",
    ],
)
def test_extract_public_id_rejects_non_profiles(url: str) -> None:
    with pytest.raises(InvalidProfileUrlError):
        extract_public_id(url)
