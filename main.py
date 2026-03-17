import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import database
import monitor
import aggregation
from api import init_routers
from version import API_VERSION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle.

    Handles startup and shutdown of the FastAPI application:
    - On startup: Loads configuration, initializes database, starts monitoring service
    - On shutdown: Cancels the monitoring service

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None
    """
    monitors_config, app_config, _ = config.load_config()
    database.init_db()
    aggregation.merge_duplicate_aggregates(database.engine, app_config)
    aggregation.backfill_missing_aggregates(database.engine, app_config)
    task = asyncio.create_task(monitor.monitor_service(monitors_config, app_config))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app():
    """Create and configure the FastAPI application.

    Sets up the FastAPI app with:
    - CORS middleware for cross-origin requests
    - All API routers
    - Proper error handling for configuration issues

    Returns:
        FastAPI: Configured FastAPI application instance.

    Raises:
        FileNotFoundError: If config.yaml is not found.
        Exception: For other configuration-related errors.
    """
    app = FastAPI(
        title="甘いStatus API",
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    try:
        monitors_config, app_config, _ = config.load_config()

        routers = init_routers(monitors_config, app_config)
        for router in routers:
            app.include_router(router)
    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please ensure config.yaml exists in the project root")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    monitors_config, app_config, server_config = config.load_config()
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8182)

    uvicorn.run(app, host=host, port=port)
