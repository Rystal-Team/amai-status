from fastapi import APIRouter, Request
from pydantic import BaseModel

from .models import HealthResponse
from version import API_VERSION

router = APIRouter(tags=["Health"])


class VersionResponse(BaseModel):
    """API version information."""

    api_version: str
    status: str = "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=200,
    summary="Health check",
    description="Check if the API service is running",
)
def health_check():
    """Health check endpoint.

    Simple endpoint to verify that the API service is running and responsive.

    Returns:
        HealthResponse: Health status response.
    """
    return {"status": "ok"}


@router.get(
    "/version",
    response_model=VersionResponse,
    status_code=200,
    summary="API version",
    description="Get API version information",
)
def get_version():
    """Get API version information.

    Returns the current version of the API.

    Returns:
        VersionResponse: API version information with status.
    """
    return {"api_version": API_VERSION, "status": "ok"}


class ClientIPResponse(BaseModel):
    """Client IP information."""

    client_ip: str
    status: str = "ok"


@router.get(
    "/client-ip",
    response_model=ClientIPResponse,
    status_code=200,
    summary="Client IP address",
    description="Get the client's IP address as seen by the server",
)
def get_client_ip(request: Request):
    """Get client IP address.

    Returns the IP address of the client making the request.
    Handles X-Forwarded-For header for requests through proxies.

    Args:
        request (Request): The incoming request object.

    Returns:
        ClientIPResponse: Client IP address information.
    """
    client_ip = request.headers.get("X-Forwarded-For")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    return {"client_ip": client_ip, "status": "ok"}
