"""Description: Create initial database schema with monitor_records table."""

from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MonitorRecord(Base):
    """Initial monitor records table schema."""

    __tablename__ = "monitor_records"
    id = Column(Integer, primary_key=True, index=True)
    monitor_name = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    status_code = Column(Integer, nullable=True)
    is_up = Column(Boolean)
    response_time = Column(Float, nullable=True)


def upgrade(engine):
    """Apply migration."""
    Base.metadata.create_all(bind=engine)


def downgrade(engine):
    """Revert migration."""
    Base.metadata.drop_all(bind=engine)
