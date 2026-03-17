from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta

from .utils import aggregate_heartbeat_data
import database

router = APIRouter(prefix="/api/heartbeat", tags=["Status"])


def create_heartbeat_router(app_config: dict):
    """Create heartbeat router with config dependency.

    Factory function that creates an APIRouter for heartbeat endpoints.
    Provides aggregated heartbeat data for monitors at various time intervals.

    Args:
        app_config (dict): Application configuration containing degraded thresholds.

    Returns:
        APIRouter: Configured router with heartbeat endpoints.
    """

    valid_intervals = ["all", "hour", "day", "week"]
    default_hours_by_interval = {
        "all": 30 * 24,
        "hour": 96,
        "day": 120 * 24,
        "week": 104 * 7 * 24,
    }

    @router.get(
        "",
        response_model=dict,
        status_code=200,
        summary="Get aggregated heartbeat data for a monitor",
        description="Get heartbeat data aggregated by time interval",
    )
    def get_aggregated_heartbeat(
        monitor_name: str, interval: str = "all", hours: int = 24
    ):
        """Get aggregated heartbeat data for a specific monitor.

        Aggregates heartbeat records by the specified time interval, providing
        a summary view of monitor performance over the requested period.

        Args:
            monitor_name (str): Name of the monitor to query.
            interval (str): Time interval ('all', 'hour', 'day', 'week'). Default: 'all'.
            hours (int): Number of hours to look back (default: 24).

        Returns:
            dict: Dictionary with monitor_name, interval, and aggregated heartbeat data.

        Raises:
            HTTPException: 400 if invalid interval, 404 if monitor not found.
        """
        from .models import MonitorRecord

        if interval not in valid_intervals:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}",
            )

        db = database.SessionLocal()
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            records = (
                db.query(MonitorRecord)
                .filter(
                    MonitorRecord.monitor_name == monitor_name,
                    MonitorRecord.timestamp >= cutoff_time,
                )
                .order_by(MonitorRecord.timestamp.asc())
                .all()
            )

            if not records:
                raise HTTPException(
                    status_code=404,
                    detail=f"Monitor '{monitor_name}' not found or no data available",
                )

            aggregated_data = aggregate_heartbeat_data(records, interval, app_config)

            return {
                "monitor_name": monitor_name,
                "interval": interval,
                "heartbeat": aggregated_data,
            }
        finally:
            db.close()

    @router.get(
        "/bulk",
        response_model=dict,
        status_code=200,
        summary="Get precomputed heartbeat data for monitors",
        description=(
            "Get heartbeat data precomputed for multiple monitors and intervals in one request"
        ),
    )
    def get_bulk_aggregated_heartbeat(
        monitor_names: str = "",
        intervals: str = "all,hour,day,week",
    ):
        """Get precomputed heartbeat data for many monitors and intervals.

        Uses a single database query for the maximum required lookback window,
        then computes all requested interval aggregations in-memory.

        Args:
            monitor_names (str): Comma-separated monitor names. Empty means all monitors.
            intervals (str): Comma-separated intervals. Defaults to all supported intervals.

        Returns:
            dict: Timestamp and a nested map keyed by monitor then interval.

        Raises:
            HTTPException: 400 if interval list contains unsupported values.
        """
        from .models import MonitorRecord

        requested_intervals = [i.strip() for i in intervals.split(",") if i.strip()]
        if not requested_intervals:
            requested_intervals = ["all"]

        invalid_intervals = [i for i in requested_intervals if i not in valid_intervals]
        if invalid_intervals:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid intervals: "
                    f"{', '.join(invalid_intervals)}. Must be one of: {', '.join(valid_intervals)}"
                ),
            )

        requested_monitor_names = [
            m.strip() for m in monitor_names.split(",") if m.strip()
        ]

        hours_by_interval = {
            interval: default_hours_by_interval[interval]
            for interval in requested_intervals
        }
        now = datetime.now()
        max_hours = max(hours_by_interval.values())
        max_cutoff = now - timedelta(hours=max_hours)

        db = database.SessionLocal()
        try:
            query = db.query(MonitorRecord).filter(MonitorRecord.timestamp >= max_cutoff)
            if requested_monitor_names:
                query = query.filter(
                    MonitorRecord.monitor_name.in_(requested_monitor_names)
                )

            all_records = (
                query.order_by(
                    MonitorRecord.monitor_name.asc(), MonitorRecord.timestamp.asc()
                ).all()
            )

            records_by_monitor = {}
            for record in all_records:
                records_by_monitor.setdefault(record.monitor_name, []).append(record)

            target_monitors = requested_monitor_names or sorted(records_by_monitor.keys())
            precomputed = {}

            for monitor_name in target_monitors:
                monitor_records = records_by_monitor.get(monitor_name, [])
                precomputed[monitor_name] = {}

                for interval in requested_intervals:
                    interval_cutoff = now - timedelta(hours=hours_by_interval[interval])
                    interval_records = [
                        r for r in monitor_records if r.timestamp >= interval_cutoff
                    ]
                    precomputed[monitor_name][interval] = aggregate_heartbeat_data(
                        interval_records, interval, app_config
                    )

            return {
                "timestamp": now.isoformat(),
                "interval_hours": hours_by_interval,
                "data": precomputed,
            }
        finally:
            db.close()

    return router
