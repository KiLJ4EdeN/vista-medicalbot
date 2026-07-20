class ServiceError(Exception):
    """Base error raised by application services."""


class AuthenticationError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class InactiveUserError(AuthenticationError):
    pass


class TokenError(AuthenticationError):
    pass


class NotFoundError(ServiceError):
    pass


class InvalidInputError(ServiceError):
    pass


class ExternalServiceError(ServiceError):
    pass
