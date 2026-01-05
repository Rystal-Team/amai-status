from datetime import timedelta
from typing import List

from .models import MonitorRecord


def aggregate_heartbeat_data(
    records: List[MonitorRecord], interval: str, app_config: dict
) -> List[dict]:
    """
    Aggregate heartbeat records by time interval.

    Args:
        records: List of monitor records
        interval: Time interval ('all', 'hour', 'day', 'week')
        app_config: Application configuration

    Returns:
        List of aggregated heartbeat nodes with status and metadata
    """
    if not records:
        return []

    if interval == "all":
        degraded_threshold = app_config.get("degraded_threshold", 200) / 1000
        aggregated = []
        for r in records:
            is_degraded = (
                r.is_up
                and r.response_time is not None
                and r.response_time > degraded_threshold
            )
            aggregated.append(
                {
                    "timestamp": r.timestamp.isoformat(),
                    "is_up": r.is_up,
                    "response_time": r.response_time,
                    "status_code": r.status_code,
                    "count": 1,
                    "avg_response_time": r.response_time,
                    "degraded_count": 1 if is_degraded else 0,
                    "down_count": 0 if r.is_up else 1,
                }
            )
        return aggregated

    interval_mapping = {
        "hour": timedelta(hours=1),
        "day": timedelta(days=1),
        "week": timedelta(weeks=1),
    }

    delta = interval_mapping.get(interval, timedelta(hours=1))

    grouped: dict = {}
    for r in records:
        if interval == "hour":
            start = r.timestamp.replace(minute=0, second=0, microsecond=0)
        elif interval == "day":
            start = r.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif interval == "week":
            start = r.timestamp - timedelta(days=r.timestamp.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = r.timestamp

        key = start.isoformat()
        if key not in grouped:
            grouped[key] = {
                "timestamp": key,
                "records": [],
                "start_time": start,
            }
        grouped[key]["records"].append(r)

    aggregated = []
    degraded_threshold = app_config.get("degraded_threshold", 200) / 1000
    degraded_percentage_threshold = app_config.get("degraded_percentage_threshold", 10)
    for key in sorted(grouped.keys()):
        group = grouped[key]
        recs = group["records"]

        up_count = sum(1 for r in recs if r.is_up)
        down_count = len(recs) - up_count

        response_times = [r.response_time for r in recs if r.response_time is not None]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else None
        )

        degraded_count = sum(
            1
            for r in recs
            if r.is_up
            and r.response_time is not None
            and r.response_time > degraded_threshold
        )

        total_issues = down_count + degraded_count
        issue_percentage = (total_issues / len(recs)) * 100 if recs else 0

        if down_count > 0:
            status = "down"
        elif issue_percentage > degraded_percentage_threshold:
            status = "degraded"
        else:
            status = "up"

        aggregated.append(
            {
                "timestamp": key,
                "is_up": status == "up",
                "status": status,
                "response_time": avg_response_time,
                "count": len(recs),
                "avg_response_time": avg_response_time,
                "degraded_count": degraded_count,
                "down_count": down_count,
                "issue_percentage": issue_percentage,
            }
        )

    return aggregated
