class DuplicateResourceError(Exception):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message)
