class DuplicateResourceError(Exception):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message)


class InvalidCredentialsError(Exception):
    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(message)


class ResumeUploadLimitExceeded(Exception):
    def __init__(self, message: str = "Daily resume upload limit reached") -> None:
        super().__init__(message)


class AIExtractionError(Exception):
    """Raised when the AI provider (Gemini) fails or returns something we
    can't use -- covers both outright failures and a resume PDF that yielded
    no extractable text. Routes translate this to a 502, not a raw 500, so
    the user sees "couldn't process your resume, try again" instead of a
    generic server error."""

    def __init__(self, message: str = "Could not process the resume") -> None:
        super().__init__(message)
