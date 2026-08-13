class DuplicateResourceError(Exception):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message)


class InvalidCredentialsError(Exception):
    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(message)
