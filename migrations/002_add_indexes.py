"""Description: Add composite indexes and optimize queries for better performance."""

from sqlalchemy import text


def upgrade(engine):
    """Apply migration - add indexes for optimization."""
    with engine.connect() as connection:
        try:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_monitor_timestamp "
                    "ON monitor_records(monitor_name, timestamp DESC)"
                )
            )
        except Exception:
            pass

        try:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_is_up " "ON monitor_records(is_up)"
                )
            )
        except Exception:
            pass

        try:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_timestamp_desc "
                    "ON monitor_records(timestamp DESC)"
                )
            )
        except Exception:
            pass

        connection.commit()


def downgrade(engine):
    """Revert migration - drop indexes."""
    with engine.connect() as connection:
        try:
            connection.execute(text("DROP INDEX IF EXISTS idx_monitor_timestamp"))
        except Exception:
            pass

        try:
            connection.execute(text("DROP INDEX IF EXISTS idx_is_up"))
        except Exception:
            pass

        try:
            connection.execute(text("DROP INDEX IF EXISTS idx_timestamp_desc"))
        except Exception:
            pass

        connection.commit()
