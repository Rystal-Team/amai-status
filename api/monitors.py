from fastapi import APIRouter
from typing import List

from .models import MonitorInfo

router = APIRouter(prefix="/api/monitors", tags=["Monitors"])


def create_monitors_router(monitors_config: list):
    """Create monitors router with config dependency.

    Factory function that creates an APIRouter for monitors endpoints.
    The router provides access to the list of configured monitors.

    Args:
        monitors_config (list): List of monitor configurations to serve.

    Returns:
        APIRouter: Configured router with monitors endpoints.
    """

    @router.get(
        "",
        response_model=List[MonitorInfo],
        status_code=200,
        summary="List all monitors",
        description="Get a list of all configured monitors",
    )
    def get_monitors():
        """Get list of all monitors.

        Returns a list of all monitors that are being monitored by the system.

        Returns:
            list: List of MonitorInfo objects with monitor names.
        """
        return [{"name": m["name"]} for m in monitors_config]

    return router
