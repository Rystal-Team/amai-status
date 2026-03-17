from datetime import datetime, timedelta
import logging
from sqlalchemy import text

from api.models import HeartbeatAggregate, MonitorRecord

logger = logging.getLogger(__name__)

AGGREGATE_INTERVALS = ("hour", "day", "week")


def _serialize_bucket_start(bucket_start: datetime) -> str:
    """Return canonical SQLite bucket datetime string.

    SQLite DateTime values can be persisted in multiple textual formats.
    Using one canonical format prevents logically-identical buckets from
    bypassing the unique constraint due to string differences.
    """
    return bucket_start.strftime("%Y-%m-%d %H:%M:%S")


def get_bucket_start(timestamp: datetime, interval: str) -> datetime:
    """Return normalized bucket start for an interval."""
    if interval == "hour":
        return timestamp.replace(minute=0, second=0, microsecond=0)
    if interval == "day":
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    if interval == "week":
        start = timestamp - timedelta(days=timestamp.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported interval: {interval}")


def _compute_status(count: int, down_count: int, degraded_count: int, threshold: float):
    issue_percentage = ((down_count + degraded_count) * 100.0 / count) if count else 0.0
    if down_count > 0:
        status = "down"
    elif issue_percentage > threshold:
        status = "degraded"
    else:
        status = "up"
    return status, issue_percentage


def upsert_aggregates_for_record(db, record: MonitorRecord, app_config: dict):
    """Incrementally update hour/day/week aggregate buckets for one monitor record."""
    degraded_threshold_seconds = app_config.get("degraded_threshold", 200) / 1000
    degraded_percentage_threshold = app_config.get("degraded_percentage_threshold", 10)
    now = datetime.now()

    is_degraded = (
        record.is_up
        and record.response_time is not None
        and record.response_time > degraded_threshold_seconds
    )

    for interval in AGGREGATE_INTERVALS:
        bucket_start = get_bucket_start(record.timestamp, interval)
        bucket_start_str = _serialize_bucket_start(bucket_start)
        aggregate = (
            db.query(HeartbeatAggregate)
            .filter(
                HeartbeatAggregate.monitor_name == record.monitor_name,
                HeartbeatAggregate.interval == interval,
                HeartbeatAggregate.bucket_start == bucket_start_str,
            )
            .one_or_none()
        )

        if aggregate is None:
            response_sample_count = 1 if record.response_time is not None else 0
            avg_response_time = (
                record.response_time if record.response_time is not None else None
            )
            count = 1
            down_count = 0 if record.is_up else 1
            degraded_count = 1 if is_degraded else 0

            status, issue_percentage = _compute_status(
                count, down_count, degraded_count, degraded_percentage_threshold
            )
            aggregate = HeartbeatAggregate(
                monitor_name=record.monitor_name,
                interval=interval,
                bucket_start=bucket_start_str,
                count=count,
                down_count=down_count,
                degraded_count=degraded_count,
                response_sample_count=response_sample_count,
                avg_response_time=avg_response_time,
                issue_percentage=issue_percentage,
                status=status,
                is_up=status == "up",
                updated_at=now,
            )
            db.add(aggregate)
            continue

        aggregate.count += 1
        if not record.is_up:
            aggregate.down_count += 1
        if is_degraded:
            aggregate.degraded_count += 1

        if record.response_time is not None:
            prev_samples = aggregate.response_sample_count
            prev_total = (aggregate.avg_response_time or 0.0) * prev_samples
            aggregate.response_sample_count = prev_samples + 1
            aggregate.avg_response_time = (
                prev_total + record.response_time
            ) / aggregate.response_sample_count

        status, issue_percentage = _compute_status(
            aggregate.count,
            aggregate.down_count,
            aggregate.degraded_count,
            degraded_percentage_threshold,
        )
        aggregate.issue_percentage = issue_percentage
        aggregate.status = status
        aggregate.is_up = status == "up"
        aggregate.updated_at = now


def merge_duplicate_aggregates(engine, app_config: dict):
    """Merge duplicate aggregate buckets created with mixed timestamp formats."""
    degraded_percentage_threshold = app_config.get("degraded_percentage_threshold", 10)

    duplicate_groups_query = text(
        """
        SELECT
            monitor_name,
            interval,
            datetime(bucket_start) AS normalized_bucket_start,
            MIN(id) AS keep_id,
            COUNT(*) AS row_count,
            SUM(count) AS total_count,
            SUM(down_count) AS total_down_count,
            SUM(degraded_count) AS total_degraded_count,
            SUM(response_sample_count) AS total_response_samples,
            SUM(COALESCE(avg_response_time, 0) * COALESCE(response_sample_count, 0)) AS total_response_sum,
            MAX(updated_at) AS latest_updated_at
        FROM heartbeat_aggregates
        GROUP BY monitor_name, interval, datetime(bucket_start)
        HAVING COUNT(*) > 1
        """
    )

    with engine.connect() as connection:
        duplicate_groups = connection.execute(duplicate_groups_query).mappings().all()
        if not duplicate_groups:
            return

        deleted_rows = 0

        for group in duplicate_groups:
            total_count = int(group["total_count"] or 0)
            total_down_count = int(group["total_down_count"] or 0)
            total_degraded_count = int(group["total_degraded_count"] or 0)
            total_response_samples = int(group["total_response_samples"] or 0)

            avg_response_time = (
                float(group["total_response_sum"]) / total_response_samples
                if total_response_samples > 0
                else None
            )

            status, issue_percentage = _compute_status(
                total_count,
                total_down_count,
                total_degraded_count,
                degraded_percentage_threshold,
            )

            connection.execute(
                text(
                    """
                    UPDATE heartbeat_aggregates
                    SET
                        bucket_start = :normalized_bucket_start,
                        count = :total_count,
                        down_count = :total_down_count,
                        degraded_count = :total_degraded_count,
                        response_sample_count = :total_response_samples,
                        avg_response_time = :avg_response_time,
                        issue_percentage = :issue_percentage,
                        status = :status,
                        is_up = :is_up,
                        updated_at = :updated_at
                    WHERE id = :keep_id
                    """
                ),
                {
                    "normalized_bucket_start": group["normalized_bucket_start"],
                    "total_count": total_count,
                    "total_down_count": total_down_count,
                    "total_degraded_count": total_degraded_count,
                    "total_response_samples": total_response_samples,
                    "avg_response_time": avg_response_time,
                    "issue_percentage": issue_percentage,
                    "status": status,
                    "is_up": 1 if status == "up" else 0,
                    "updated_at": group["latest_updated_at"] or datetime.now(),
                    "keep_id": group["keep_id"],
                },
            )

            delete_result = connection.execute(
                text(
                    """
                    DELETE FROM heartbeat_aggregates
                    WHERE
                        monitor_name = :monitor_name
                        AND interval = :interval
                        AND datetime(bucket_start) = :normalized_bucket_start
                        AND id != :keep_id
                    """
                ),
                {
                    "monitor_name": group["monitor_name"],
                    "interval": group["interval"],
                    "normalized_bucket_start": group["normalized_bucket_start"],
                    "keep_id": group["keep_id"],
                },
            )
            deleted_rows += delete_result.rowcount or 0

        connection.commit()
        logger.info(
            "Merged %s duplicate aggregate groups and deleted %s rows",
            len(duplicate_groups),
            deleted_rows,
        )


def backfill_missing_aggregates(engine, app_config: dict):
    """Backfill precomputed buckets from historical monitor records.

    Uses INSERT OR IGNORE so existing aggregate buckets are preserved and only
    missing buckets from pre-upgrade history are inserted.
    """
    degraded_threshold_seconds = app_config.get("degraded_threshold", 200) / 1000
    degraded_percentage_threshold = app_config.get("degraded_percentage_threshold", 10)

    bucket_expr = {
        "hour": "strftime('%Y-%m-%d %H:00:00', timestamp)",
        "day": "strftime('%Y-%m-%d 00:00:00', timestamp)",
        "week": (
            "strftime('%Y-%m-%d 00:00:00', "
            "datetime(timestamp, '-' || ((cast(strftime('%w', timestamp) as integer) + 6) % 7) || ' days'))"
        ),
    }

    with engine.connect() as connection:
        existing_count = connection.execute(
            text("SELECT COUNT(1) FROM heartbeat_aggregates")
        ).scalar()
        if existing_count and existing_count > 0:
            logger.info(
                "Skipping aggregate backfill because %s aggregate rows already exist",
                existing_count,
            )
            return

        for interval in AGGREGATE_INTERVALS:
            expr = bucket_expr[interval]
            query = text(
                f"""
                INSERT OR IGNORE INTO heartbeat_aggregates (
                    monitor_name,
                    interval,
                    bucket_start,
                    count,
                    down_count,
                    degraded_count,
                    response_sample_count,
                    avg_response_time,
                    issue_percentage,
                    status,
                    is_up,
                    updated_at
                )
                SELECT
                    grouped.monitor_name,
                    :interval AS interval,
                    grouped.bucket_start,
                    grouped.total_count,
                    grouped.down_count,
                    grouped.degraded_count,
                    grouped.response_sample_count,
                    grouped.avg_response_time,
                    CASE
                        WHEN grouped.total_count > 0
                            THEN ((grouped.down_count + grouped.degraded_count) * 100.0 / grouped.total_count)
                        ELSE 0
                    END AS issue_percentage,
                    CASE
                        WHEN grouped.down_count > 0 THEN 'down'
                        WHEN (
                            CASE
                                WHEN grouped.total_count > 0
                                    THEN ((grouped.down_count + grouped.degraded_count) * 100.0 / grouped.total_count)
                                ELSE 0
                            END
                        ) > :degraded_percentage_threshold THEN 'degraded'
                        ELSE 'up'
                    END AS status,
                    CASE
                        WHEN grouped.down_count = 0 AND (
                            CASE
                                WHEN grouped.total_count > 0
                                    THEN ((grouped.down_count + grouped.degraded_count) * 100.0 / grouped.total_count)
                                ELSE 0
                            END
                        ) <= :degraded_percentage_threshold THEN 1
                        ELSE 0
                    END AS is_up,
                    CURRENT_TIMESTAMP AS updated_at
                FROM (
                    SELECT
                        monitor_name,
                        {expr} AS bucket_start,
                        COUNT(*) AS total_count,
                        SUM(CASE WHEN is_up = 0 THEN 1 ELSE 0 END) AS down_count,
                        SUM(
                            CASE
                                WHEN is_up = 1
                                    AND response_time IS NOT NULL
                                    AND response_time > :degraded_threshold_seconds
                                THEN 1
                                ELSE 0
                            END
                        ) AS degraded_count,
                        SUM(CASE WHEN response_time IS NOT NULL THEN 1 ELSE 0 END) AS response_sample_count,
                        AVG(response_time) AS avg_response_time
                    FROM monitor_records
                    GROUP BY monitor_name, {expr}
                ) AS grouped
                """
            )

            result = connection.execute(
                query,
                {
                    "interval": interval,
                    "degraded_threshold_seconds": degraded_threshold_seconds,
                    "degraded_percentage_threshold": degraded_percentage_threshold,
                },
            )
            logger.info(
                "Backfill interval %s inserted %s missing aggregate buckets",
                interval,
                result.rowcount,
            )

        connection.commit()
