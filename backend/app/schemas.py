from pydantic import BaseModel, ConfigDict, Field


class ProfileRequest(BaseModel):
    url: str = Field(..., examples=["https://www.linkedin.com/in/williamhgates/"])


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
    """Canonical nested profile model (internal + default adapter output)."""

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


class AdapterInfo(BaseModel):
    name: str
    description: str


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
    defaultAdapter: str = "default"
