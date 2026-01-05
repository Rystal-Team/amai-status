from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta

from .models import AllStatusResponse
import database

router = APIRouter(prefix="/api/status", tags=["Status"])


def create_status_router(monitors_config: list):
    """Create status router with config dependency.

    Factory function that creates an APIRouter for status endpoints.
    Provides detailed status history for individual monitors and all monitors.

    Args:
        monitors_config (list): List of monitor configurations.

    Returns:
        APIRouter: Configured router with status endpoints.
    """

    @router.get(
        "/{monitor_name}",
        response_model=dict,
        status_code=200,
        summary="Get monitor status history",
        description="Get detailed status history for a specific monitor",
    )
    def get_monitor_status(monitor_name: str, hours: int = 24):
        """Get status history for a specific monitor.

        Retrieves detailed status history for the specified monitor over the
        specified time period.

        Args:
            monitor_name (str): Name of the monitor to query.
            hours (int): Number of hours to look back (default: 24).

        Returns:
            dict: Dictionary with monitor_name and list of status records.

        Raises:
            HTTPException: 404 if monitor not found or no data available.
        """
        from .models import MonitorRecord

        db = database.SessionLocal()
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            records = (
                db.query(MonitorRecord)
                .filter(
                    MonitorRecord.monitor_name == monitor_name,
                    MonitorRecord.timestamp >= cutoff_time,
                )
                .order_by(MonitorRecord.timestamp.desc())
                .all()
            )

            if not records:
                raise HTTPException(
                    status_code=404, detail=f"Monitor '{monitor_name}' not found"
                )

            return {
                "monitor_name": monitor_name,
                "records": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "status_code": r.status_code,
                        "is_up": r.is_up,
                        "response_time": r.response_time,
                    }
                    for r in records
                ],
            }
        finally:
            db.close()

    @router.get(
        "",
        response_model=AllStatusResponse,
        status_code=200,
        summary="Get all monitors status",
        description="Get current status and history for all configured monitors",
    )
    def get_all_status(hours: int = 24):
        """Get current status and history for all monitors.

        Returns the current status and detailed history for all configured monitors
        over the specified time period.

        Args:
            hours (int): Number of hours to look back (default: 24).

        Returns:
            AllStatusResponse: Response containing timestamp and all monitors status.
        """
        from .models import MonitorRecord

        db = database.SessionLocal()
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            monitors_status = []
            for monitor in monitors_config:
                records = (
                    db.query(MonitorRecord)
                    .filter(
                        MonitorRecord.monitor_name == monitor["name"],
                        MonitorRecord.timestamp >= cutoff_time,
                    )
                    .order_by(MonitorRecord.timestamp.asc())
                    .all()
                )

                latest = None
                if records:
                    latest = records[-1]

                monitor_data = {
                    "name": monitor["name"],
                    "url": monitor["url"],
                    "current_status": {
                        "is_up": latest.is_up if latest else None,
                        "status_code": latest.status_code if latest else None,
                        "response_time": latest.response_time if latest else None,
                        "timestamp": latest.timestamp.isoformat() if latest else None,
                    },
                    "history": [
                        {
                            "timestamp": r.timestamp.isoformat(),
                            "is_up": r.is_up,
                            "status_code": r.status_code,
                            "response_time": r.response_time,
                        }
                        for r in records
                    ],
                }
                monitors_status.append(monitor_data)

            return {
                "timestamp": datetime.now().isoformat(),
                "monitors": monitors_status,
            }
        finally:
            db.close()

    return router
