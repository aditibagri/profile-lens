class LinkedInError(Exception):
    """Mapped to an HTTP error by the FastAPI exception handler."""

    def __init__(self, message: str, status_code: int = 502, code: str = "upstream_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class InvalidProfileUrlError(LinkedInError):
    def __init__(self, message: str = "Provide a public LinkedIn profile URL (/in/{slug})."):
        super().__init__(message, status_code=400, code="invalid_url")


class SessionExpiredError(LinkedInError):
    def __init__(self, message: str = "LinkedIn signed you out. Connect again on this page."):
        super().__init__(message, status_code=401, code="session_expired")


class ProfileNotFoundError(LinkedInError):
    def __init__(self, message: str = "LinkedIn profile not found or is not visible to this session."):
        super().__init__(message, status_code=404, code="not_found")


class LinkedInRateLimitError(LinkedInError):
    def __init__(self, message: str = "LinkedIn rate-limited this session. Try again later."):
        super().__init__(message, status_code=429, code="linkedin_rate_limited")


class NotConfiguredError(LinkedInError):
    def __init__(
        self,
        message: str = "Connect LinkedIn on this page first (extension or paste cookies).",
    ):
        super().__init__(message, status_code=503, code="not_configured")
