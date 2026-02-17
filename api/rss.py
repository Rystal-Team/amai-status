from fastapi import APIRouter
from fastapi.responses import Response
from datetime import timezone

import database

router = APIRouter(tags=["RSS"])


def create_rss_router(monitors_config: list):
    """Create RSS router with config dependency.

    Factory function that creates an APIRouter for RSS feed endpoint.
    Provides an RSS feed of recent monitor status updates.

    Args:
        monitors_config (list): List of monitor configurations.

    Returns:
        APIRouter: Configured router with RSS feed endpoint.
    """

    @router.get(
        "/rss",
        status_code=200,
        summary="Get RSS feed",
        description="Get RSS feed of monitor status updates",
    )
    def get_rss_feed():
        """Get RSS feed of monitor status updates.

        Returns an RSS feed containing recent status changes for all monitors,
        fetching the 100 most recent status records from the database.

        Returns:
            Response: RSS feed as XML with media type application/rss+xml.
        """
        from feedgen.feed import FeedGenerator
        from .models import MonitorRecord

        db = database.SessionLocal()
        try:
            fg = FeedGenerator()
            fg.id("http://localhost")
            fg.title("Status Feed")
            fg.link(href="http://localhost", rel="alternate")
            fg.description("Status updates for all monitors")

            all_records = (
                db.query(MonitorRecord)
                .order_by(MonitorRecord.timestamp.desc())
                .limit(100)
                .all()
            )

            for record in all_records:
                monitor_name = record.monitor_name
                status_text = "UP" if record.is_up else "DOWN"

                monitor_config = next(
                    (m for m in monitors_config if m["name"] == monitor_name), None
                )

                fe = fg.add_entry()
                fe.id(f"{monitor_name}-{record.timestamp.isoformat()}")
                fe.title(f"{monitor_name}: {status_text}")
                fe.link(
                    href="", rel="alternate"
                )  # Hide actual link for security/privacy
                fe.description(
                    f"Status: {status_text}<br/>"
                    f"Status Code: {record.status_code or 'N/A'}<br/>"
                    f"Response Time: {record.response_time*1000:.0f}ms"
                    if record.response_time
                    else "Response Time: N/A"
                )
                fe.pubDate(record.timestamp.replace(tzinfo=timezone.utc))

            rss_str = fg.rss_str(pretty=True)
            return Response(
                content=rss_str, media_type="application/rss+xml; charset=utf-8"
            )
        finally:
            db.close()

    return router
