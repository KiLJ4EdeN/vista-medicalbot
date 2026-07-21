from fastapi import Request, status
from fastapi.responses import JSONResponse

from core.exceptions import (
    AuthenticationError,
    ConflictError,
    ExternalServiceError,
    InactiveUserError,
    NotFoundError,
    ServiceError,
)


async def service_error_handler(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ServiceError):
        raise error
    if isinstance(error, ConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(error, NotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, ExternalServiceError):
        status_code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(error, InactiveUserError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(error, AuthenticationError):
        status_code = status.HTTP_401_UNAUTHORIZED
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return JSONResponse(status_code=status_code, content={"detail": str(error)})
