class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__("NOT_FOUND", message, 404)


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to do that") -> None:
        super().__init__("FORBIDDEN", message, 403)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("CONFLICT", message, 409)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("SERVICE_UNAVAILABLE", message, 503)