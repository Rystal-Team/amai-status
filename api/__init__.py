from .monitors import create_monitors_router
from .status import create_status_router
from .heartbeat import create_heartbeat_router
from .config import create_config_router
from .health import router as health_router
from .rss import create_rss_router
from .assets import create_assets_router


def init_routers(monitors_config: list, app_config: dict):
    """Initialize all API routers with dependencies.

    Creates and registers all route handlers with their respective configuration
    dependencies, ensuring each router has access to the monitors configuration
    and application settings.

    Args:
        monitors_config (list): List of monitor configurations containing name, url, and interval.
        app_config (dict): Application configuration including degraded thresholds and footer text.

    Returns:
        list: List of initialized APIRouter instances ready to be included in the FastAPI app.
    """
    routers = [
        create_monitors_router(monitors_config),
        create_status_router(monitors_config),
        create_heartbeat_router(app_config),
        create_config_router(app_config),
        create_rss_router(monitors_config),
        create_assets_router(),
        health_router,
    ]
    return routers
