from pydantic import BaseModel, ConfigDict, Field

from app.adapters.mapping_schema import MappingDocument


class LinkedInSessionIn(BaseModel):
    """Visitor-supplied session. Used for that request only — never stored."""

    model_config = ConfigDict(extra="ignore")

    liAt: str = ""
    jsessionid: str = ""
    userAgent: str = ""
    liap: str = ""
    bcookie: str = ""
    lidc: str = ""
    liA: str = ""


class ProfileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str = Field(..., examples=["https://www.linkedin.com/in/williamhgates/"])
    session: LinkedInSessionIn | None = None
    mapping: MappingDocument | None = Field(
        default=None,
        alias="schema",
        description="Required when adapter=custom. Maps your JSON keys to canonical profile paths.",
    )


class DateRange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start: str | None = None
    end: str | None = None
    current: bool = False


class Experience(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    company: str | None = None
    companyUrl: str | None = None
    location: str | None = None
    description: str | None = None
    employmentType: str | None = None
    dateRange: DateRange | None = None
    companyLogo: str | None = None


class Education(BaseModel):
    model_config = ConfigDict(extra="ignore")

    school: str | None = None
    degree: str | None = None
    fieldOfStudy: str | None = None
    description: str | None = None
    dateRange: DateRange | None = None
    schoolLogo: str | None = None


class Skill(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    endorsementCount: int | None = None


class Certification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    issuer: str | None = None
    licenseNumber: str | None = None
    url: str | None = None
    issuedOn: str | None = None
    expiresOn: str | None = None


class Language(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    proficiency: str | None = None


class Volunteer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str | None = None
    organization: str | None = None
    cause: str | None = None
    description: str | None = None
    dateRange: DateRange | None = None


class Honor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    issuer: str | None = None
    description: str | None = None
    issuedOn: str | None = None


class ProfileResponse(BaseModel):
    """Canonical nested profile parsed from LinkedIn. Adapters map this via JSON."""

    model_config = ConfigDict(extra="ignore")

    publicId: str
    profileUrl: str
    fullName: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    headline: str | None = None
    location: str | None = None
    about: str | None = None
    pronouns: str | None = None
    industry: str | None = None
    profileImage: str | None = None
    backgroundImage: str | None = None
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    volunteer: list[Volunteer] = Field(default_factory=list)
    honors: list[Honor] = Field(default_factory=list)


class AdaptedProfileResponse(BaseModel):
    """Envelope returned by /v1/profile — adapter controls the shape of `data`."""

    adapter: str
    data: dict
    source: dict | None = None


class AdapterInfo(BaseModel):
    name: str
    description: str


class SchemaFieldInfo(BaseModel):
    path: str
    label: str
    group: str


class SchemaMappingRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    to: str
    from_: str = Field(alias="from")
    label: str = ""
    transform: str | None = None
    pluck: str | list[str] | None = None
    join: str | None = None
    itemFormat: str | None = None


class SchemaPreset(BaseModel):
    description: str = ""
    fields: list[SchemaMappingRow] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    code: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    linkedinConfigured: bool


class UiConfigResponse(BaseModel):
    apiKeyRequired: bool
    linkedinConfigured: bool
    adapters: list[AdapterInfo] = Field(default_factory=list)
    defaultAdapter: str = "profilelens"
    schemaFields: list[SchemaFieldInfo] = Field(default_factory=list)
    schemaPresets: dict[str, SchemaPreset] = Field(default_factory=dict)
