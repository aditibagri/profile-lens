"""Map LinkedIn Voyager JSON (dash + legacy profileView) onto our stable schema."""

from __future__ import annotations

from typing import Any

from app.schemas import (
    Certification,
    DateRange,
    Education,
    Experience,
    Honor,
    Language,
    ProfileResponse,
    Skill,
    Volunteer,
)

PROFICIENCY_LABELS = {
    "NATIVE_OR_BILINGUAL": "Native or bilingual",
    "FULL_PROFESSIONAL": "Full professional",
    "PROFESSIONAL_WORKING": "Professional working",
    "LIMITED_WORKING": "Limited working",
    "ELEMENTARY": "Elementary",
}


def parse_profile(payload: dict[str, Any], public_id: str, profile_url: str) -> ProfileResponse:
    if _is_legacy_profile_view(payload):
        return _parse_profile_view(payload, public_id, profile_url)
    return _parse_dash(payload, public_id, profile_url)


def _is_legacy_profile_view(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("profile"), dict) and (
        "positionView" in payload or "miniProfile" in payload.get("profile", {})
    )


def _type_name(entity: dict[str, Any] | None) -> str:
    if not isinstance(entity, dict):
        return ""
    raw = entity.get("$type") or entity.get("type") or ""
    return str(raw).rsplit(".", 1)[-1]


def _index_included(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in payload.get("included") or []:
        if not isinstance(item, dict):
            continue
        for key in ("entityUrn", "urn", "objectUrn"):
            urn = item.get(key)
            if urn:
                index[str(urn)] = item
                index[f"*{urn}"] = item
    return index


def _lookup_urn(urn: str, index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not urn:
        return None
    found = index.get(urn) or index.get(f"*{urn}")
    if found:
        return found
    if urn.startswith("*"):
        return index.get(urn[1:])
    return None


def _resolve(value: Any, index: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, str):
        return _lookup_urn(value, index) or value
    if isinstance(value, dict):
        urn = value.get("entityUrn") or value.get("urn") or value.get("objectUrn") or value.get("*elements")
        if isinstance(urn, str):
            found = _lookup_urn(urn, index)
            if found:
                return {**found, **value}
        return value
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, dict):
        for key in ("text", "name", "localized", "value"):
            if key in value:
                return _text(value[key])
    return None


def _format_date(value: Any) -> str | None:
    if not isinstance(value, dict):
        return _text(value)
    year = value.get("year")
    month = value.get("month")
    if year and month:
        return f"{int(year):04d}-{int(month):02d}"
    if year:
        return str(int(year))
    return None


def _date_range(entity: dict[str, Any] | None) -> DateRange | None:
    if not isinstance(entity, dict):
        return None
    raw = entity.get("dateRange") or entity.get("timePeriod")
    if not isinstance(raw, dict):
        start = _format_date(entity.get("startDate") or entity.get("issuedOn"))
        end = _format_date(entity.get("endDate") or entity.get("expiresOn"))
        if not start and not end:
            return None
        return DateRange(start=start, end=end, current=end is None and start is not None)

    start = _format_date(raw.get("start") or raw.get("startDate"))
    end = _format_date(raw.get("end") or raw.get("endDate"))
    current = bool(raw.get("end") is None and raw.get("endDate") is None)
    if not start and not end:
        return None
    return DateRange(start=start, end=end, current=current and start is not None)


def _largest_artifact_url(vector_image: dict[str, Any] | None) -> str | None:
    if not isinstance(vector_image, dict):
        return None
    root = vector_image.get("rootUrl") or ""
    artifacts = vector_image.get("artifacts") or []
    if not artifacts:
        return _text(vector_image.get("url"))
    best = max(
        artifacts,
        key=lambda a: int(a.get("width") or 0) * int(a.get("height") or 0),
    )
    segment = best.get("fileIdentifyingUrlPathSegment") or ""
    if root and segment:
        return f"{root}{segment}"
    return _text(best.get("url"))


def _image_url(node: Any) -> str | None:
    if not node:
        return None
    if isinstance(node, str) and node.startswith("http"):
        return node
    if not isinstance(node, dict):
        return None

    for key in ("src", "logoUrl"):
        raw = node.get(key)
        if isinstance(raw, str) and raw.startswith("http"):
            return raw

    for key in (
        "displayImageReference",
        "displayImageReferenceResolutionResult",
        "displayImage",
        "vectorImage",
        "originalImage",
        "croppedImage",
        "picture",
        "logo",
        "logoV2",
        "originalLogo",
        "croppedLogo",
        "logoResolutionResult",
        "companyLogo",
        "schoolLogo",
        "miniCompany",
        "miniSchool",
        "backgroundImage",
        "image",
    ):
        nested = node.get(key)
        if nested:
            found = _image_url(nested)
            if found:
                return found

    vector = node.get("vectorImage") or node.get("com.linkedin.common.VectorImage")
    found = _largest_artifact_url(vector if isinstance(vector, dict) else None)
    if found:
        return found

    # Some payloads nest VectorImage under a typed key
    for value in node.values():
        if isinstance(value, dict) and ("artifacts" in value or "rootUrl" in value):
            found = _largest_artifact_url(value)
            if found:
                return found
    return None


_COMPANY_REF_KEYS = (
    "company",
    "*company",
    "companyUrn",
    "companyResolutionResult",
    "miniCompany",
    "*miniCompany",
)
_SCHOOL_REF_KEYS = (
    "school",
    "*school",
    "schoolUrn",
    "schoolResolutionResult",
    "miniSchool",
    "*miniSchool",
)
_DIRECT_LOGO_KEYS = (
    "logoUrl",
    "companyLogoUrl",
    "schoolLogoUrl",
    "logo",
    "logoV2",
    "companyLogo",
    "schoolLogo",
    "logoResolutionResult",
)


def _logo_by_org_name(
    name: str | None,
    included: list[dict[str, Any]],
    type_names: tuple[str, ...],
) -> str | None:
    if not name:
        return None
    needle = name.strip().lower()
    wanted = set(type_names)
    for item in included:
        if _type_name(item) not in wanted:
            continue
        item_name = _text(item.get("name") or item.get("companyName") or item.get("schoolName"))
        if item_name and item_name.strip().lower() == needle:
            found = _image_url(item)
            if found:
                return found
    return None


def _org_image(
    item: dict[str, Any],
    index: dict[str, dict[str, Any]],
    included: list[dict[str, Any]],
    *,
    kind: str,
) -> str | None:
    for key in _DIRECT_LOGO_KEYS:
        found = _image_url(item.get(key))
        if found:
            return found

    ref_keys = _COMPANY_REF_KEYS if kind == "company" else _SCHOOL_REF_KEYS
    for key in ref_keys:
        raw = item.get(key)
        if raw is None:
            continue
        org = _resolve(raw, index)
        found = _image_url(org)
        if found:
            return found

    name = _company_name(item, index)
    if kind == "school":
        name = name or _text(item.get("schoolName"))
        types = ("School", "MiniSchool")
    else:
        types = ("Company", "MiniCompany", "Organization")
    return _logo_by_org_name(name, included, types)


def _location(profile: dict[str, Any]) -> str | None:
    for key in ("geoLocationName", "locationName", "geoLocation", "location"):
        value = profile.get(key)
        text = _text(value)
        if text:
            return text
        if isinstance(value, dict):
            geo = value.get("geo") or value.get("defaultLocalizedName")
            text = _text(geo) or _text((geo or {}).get("defaultLocalizedName") if isinstance(geo, dict) else None)
            if text:
                return text
    return None


def _entities_of(included: list[Any], *names: str) -> list[dict[str, Any]]:
    wanted = set(names)
    out: list[dict[str, Any]] = []
    for item in included:
        if isinstance(item, dict) and _type_name(item) in wanted:
            out.append(item)
    return out


def _find_profile_entity(
    payload: dict[str, Any],
    index: dict[str, dict[str, Any]],
    public_id: str,
) -> dict[str, Any]:
    data = payload.get("data") or {}
    elements = data.get("elements") if isinstance(data, dict) else None
    if isinstance(elements, list) and elements:
        resolved = _resolve(elements[0], index)
        if isinstance(resolved, dict) and (
            resolved.get("firstName") or resolved.get("publicIdentifier") or _type_name(resolved) == "Profile"
        ):
            return resolved

    included = payload.get("included") or []
    for item in included:
        if not isinstance(item, dict):
            continue
        if _type_name(item) == "Profile" and (
            item.get("publicIdentifier") == public_id or item.get("firstName")
        ):
            return item
    for item in included:
        if isinstance(item, dict) and item.get("firstName") and item.get("lastName"):
            return item
    return {}


def _company_name(entity: dict[str, Any], index: dict[str, dict[str, Any]]) -> str | None:
    for key in ("companyName", "schoolName", "name"):
        text = _text(entity.get(key))
        if text:
            return text
    for key in ("company", "companyUrn", "school", "*company"):
        resolved = _resolve(entity.get(key), index)
        if isinstance(resolved, dict):
            text = _text(resolved.get("name") or resolved.get("companyName") or resolved.get("schoolName"))
            if text:
                return text
    return None


def _skill_name(item: dict[str, Any]) -> str | None:
    skill_node = item.get("skill")
    if isinstance(skill_node, dict):
        return _text(item.get("name") or skill_node.get("name"))
    return _text(item.get("name") or skill_node)


def _endorsement_count(item: dict[str, Any]) -> int | None:
    endorsements = item.get("endorsementCount") or item.get("numEndorsements")
    if isinstance(endorsements, int):
        return endorsements
    skill_node = item.get("skill")
    if isinstance(skill_node, dict):
        nested = skill_node.get("endorsementCount")
        if isinstance(nested, int):
            return nested
    return None


def _iter_skill_nodes(included: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    nodes.extend(_entities_of(included, "Skill"))
    nodes.extend(_elements(payload.get("skillView")))
    category = payload.get("skillCategoryView") or payload.get("skillCategory")
    for group in _elements(category):
        nested = group.get("endorsedSkills") or group.get("skills") or []
        if isinstance(nested, list) and nested:
            nodes.extend(item for item in nested if isinstance(item, dict))
        elif group.get("name"):
            nodes.append(group)
    return nodes


def _collect_skills(included: list[dict[str, Any]], payload: dict[str, Any]) -> list[Skill]:
    skills: list[Skill] = []
    seen: set[str] = set()
    for item in _iter_skill_nodes(included, payload):
        name = _skill_name(item)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        skills.append(Skill(name=name, endorsementCount=_endorsement_count(item)))
    return skills


def _certification_from(item: dict[str, Any]) -> Certification:
    period = item.get("timePeriod") if isinstance(item.get("timePeriod"), dict) else {}
    return Certification(
        name=_text(item.get("name") or item.get("title")),
        issuer=_text(item.get("authority") or item.get("companyName")),
        licenseNumber=_text(item.get("licenseNumber")),
        url=_text(item.get("url")),
        issuedOn=_format_date(period.get("start") if period else item.get("issuedOn")),
        expiresOn=_format_date(period.get("end") if period else item.get("expiresOn")),
    )


def _collect_certifications(included: list[dict[str, Any]], payload: dict[str, Any]) -> list[Certification]:
    certifications: list[Certification] = []
    seen: set[tuple[str, str]] = set()
    nodes = _entities_of(included, "Certification") + _elements(payload.get("certificationView"))
    for item in nodes:
        cert = _certification_from(item)
        key = ((cert.name or "").lower(), (cert.issuer or "").lower())
        if key == ("", "") or key in seen:
            continue
        seen.add(key)
        certifications.append(cert)
    return certifications


def _collect_languages(included: list[dict[str, Any]], payload: dict[str, Any]) -> list[Language]:
    languages: list[Language] = []
    seen: set[str] = set()
    nodes = _entities_of(included, "Language") + _elements(payload.get("languageView"))
    for item in nodes:
        name = _text(item.get("name"))
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        proficiency = item.get("proficiency")
        languages.append(
            Language(
                name=name,
                proficiency=PROFICIENCY_LABELS.get(str(proficiency), _text(proficiency)),
            )
        )
    return languages


def _collect_volunteer(included: list[dict[str, Any]], payload: dict[str, Any]) -> list[Volunteer]:
    volunteer: list[Volunteer] = []
    seen: set[tuple[str, str]] = set()
    nodes = _entities_of(included, "VolunteerExperience", "Volunteer") + _elements(
        payload.get("volunteerExperienceView")
    )
    for item in nodes:
        entry = Volunteer(
            role=_text(item.get("role") or item.get("title")),
            organization=_text(item.get("companyName") or item.get("organizationName")),
            cause=_text(item.get("cause")),
            description=_text(item.get("description")),
            dateRange=_date_range(item),
        )
        key = ((entry.role or "").lower(), (entry.organization or "").lower())
        if key == ("", "") or key in seen:
            continue
        seen.add(key)
        volunteer.append(entry)
    return volunteer


def _collect_honors(included: list[dict[str, Any]], payload: dict[str, Any]) -> list[Honor]:
    honors: list[Honor] = []
    seen: set[tuple[str, str]] = set()
    nodes = _entities_of(included, "Honor", "HonorAward") + _elements(payload.get("honorView"))
    for item in nodes:
        entry = Honor(
            title=_text(item.get("title") or item.get("name")),
            issuer=_text(item.get("issuer") or item.get("issuerName")),
            description=_text(item.get("description")),
            issuedOn=_format_date(item.get("issuedOn") or item.get("issueDate")),
        )
        key = ((entry.title or "").lower(), (entry.issuer or "").lower())
        if key == ("", "") or key in seen:
            continue
        seen.add(key)
        honors.append(entry)
    return honors


def _parse_dash(payload: dict[str, Any], public_id: str, profile_url: str) -> ProfileResponse:
    index = _index_included(payload)
    included = [item for item in (payload.get("included") or []) if isinstance(item, dict)]
    profile = _find_profile_entity(payload, index, public_id)

    first = _text(profile.get("firstName"))
    last = _text(profile.get("lastName"))
    full = _text(profile.get("fullName")) or " ".join(p for p in (first, last) if p) or None

    experience = []
    for item in _entities_of(included, "Position"):
        title = _text(item.get("title"))
        company = _company_name(item, index)
        if not title and not company:
            continue
        experience.append(
            Experience(
                title=title,
                company=company,
                location=_text(item.get("locationName") or item.get("geoLocationName")),
                description=_text(item.get("description")),
                employmentType=_text(item.get("employmentType") or item.get("employmentStatus")),
                dateRange=_date_range(item),
                companyLogo=_org_image(item, index, included, kind="company"),
            )
        )

    education = []
    for item in _entities_of(included, "Education"):
        school = _company_name(item, index) or _text(item.get("schoolName"))
        education.append(
            Education(
                school=school,
                degree=_text(item.get("degreeName") or item.get("degree")),
                fieldOfStudy=_text(item.get("fieldOfStudy")),
                description=_text(item.get("description")),
                dateRange=_date_range(item),
                schoolLogo=_org_image(item, index, included, kind="school"),
            )
        )

    skills = _collect_skills(included, payload)
    certifications = _collect_certifications(included, payload)
    languages = _collect_languages(included, payload)
    volunteer = _collect_volunteer(included, payload)
    honors = _collect_honors(included, payload)

    about = _text(profile.get("summary") or profile.get("about"))
    if not about:
        for item in _entities_of(included, "Profile"):
            about = _text(item.get("summary") or item.get("about"))
            if about:
                break

    return ProfileResponse(
        publicId=_text(profile.get("publicIdentifier")) or public_id,
        profileUrl=profile_url,
        fullName=full,
        firstName=first,
        lastName=last,
        headline=_text(profile.get("headline") or profile.get("occupation")),
        location=_location(profile),
        about=about,
        pronouns=_text(profile.get("pronouns") or profile.get("pronounChoice")),
        industry=_text(profile.get("industry") or profile.get("industryName")),
        profileImage=_image_url(profile.get("profilePicture") or profile.get("miniProfile")),
        backgroundImage=_image_url(profile.get("backgroundPicture") or profile.get("backgroundImage")),
        experience=experience,
        education=education,
        skills=skills,
        certifications=certifications,
        languages=languages,
        volunteer=volunteer,
        honors=honors,
    )


def _elements(view: Any) -> list[dict[str, Any]]:
    if isinstance(view, dict):
        elements = view.get("elements") or []
        return [e for e in elements if isinstance(e, dict)]
    return []


def _parse_profile_view(payload: dict[str, Any], public_id: str, profile_url: str) -> ProfileResponse:
    profile = payload.get("profile") or {}
    mini = profile.get("miniProfile") or {}
    first = _text(profile.get("firstName") or mini.get("firstName"))
    last = _text(profile.get("lastName") or mini.get("lastName"))
    full = " ".join(p for p in (first, last) if p) or None

    included = [item for item in (payload.get("included") or []) if isinstance(item, dict)]
    index = _index_included(payload)

    experience = []
    for item in _elements(payload.get("positionView")):
        company = item.get("companyName") or _text((item.get("company") or {}).get("name"))
        experience.append(
            Experience(
                title=_text(item.get("title")),
                company=_text(company),
                location=_text(item.get("locationName")),
                description=_text(item.get("description")),
                employmentType=_text(item.get("employmentType")),
                dateRange=_date_range(item),
                companyLogo=_org_image(item, index, included, kind="company"),
            )
        )

    education = []
    for item in _elements(payload.get("educationView")):
        school = item.get("schoolName") or _text((item.get("school") or {}).get("name") or (item.get("school") or {}).get("schoolName"))
        education.append(
            Education(
                school=_text(school),
                degree=_text(item.get("degreeName")),
                fieldOfStudy=_text(item.get("fieldOfStudy")),
                description=_text(item.get("description")),
                dateRange=_date_range(item),
                schoolLogo=_org_image(item, index, included, kind="school"),
            )
        )

    skills = _collect_skills(included, payload)
    certifications = _collect_certifications(included, payload)
    languages = _collect_languages(included, payload)
    volunteer = _collect_volunteer(included, payload)
    honors = _collect_honors(included, payload)

    picture = mini.get("picture") or profile.get("picture") or profile.get("profilePicture")
    background = profile.get("backgroundPicture") or profile.get("backgroundImage")

    return ProfileResponse(
        publicId=_text(mini.get("publicIdentifier") or profile.get("publicIdentifier")) or public_id,
        profileUrl=profile_url,
        fullName=full,
        firstName=first,
        lastName=last,
        headline=_text(profile.get("headline") or mini.get("occupation")),
        location=_text(profile.get("locationName") or profile.get("geoLocationName")),
        about=_text(profile.get("summary")),
        pronouns=_text(profile.get("pronouns")),
        industry=_text(profile.get("industryName")),
        profileImage=_image_url(picture),
        backgroundImage=_image_url(background),
        experience=experience,
        education=education,
        skills=skills,
        certifications=certifications,
        languages=languages,
        volunteer=volunteer,
        honors=honors,
    )
