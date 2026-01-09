from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field
from typing import Optional, List

Base = declarative_base()


class MonitorRecord(Base):
    """SQLAlchemy ORM model for monitor records.

    Represents a single monitor status check stored in the database, including
    timestamp, HTTP status code, availability, and response time.
    """

    __tablename__ = "monitor_records"
    id = Column(Integer, primary_key=True, index=True)
    monitor_name = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    status_code = Column(Integer, nullable=True)
    is_up = Column(Boolean)
    response_time = Column(Float, nullable=True)


class MonitorInfo(BaseModel):
    """Monitor information model.

    Represents basic information about a configured monitor including its name.
    """

    name: str = Field(..., description="Monitor name")

    class Config:
        json_schema_extra = {"example": {"name": "Google Search"}}


class StatusRecord(BaseModel):
    """Single status record for a monitor.

    Represents a single point-in-time status check for a monitor, including
    timestamp, availability, HTTP status code, and response time.
    """

    timestamp: str = Field(..., description="ISO format timestamp")
    is_up: bool = Field(..., description="Whether the service is up")
    status_code: Optional[int] = Field(
        None, description="HTTP status code (null if timeout/error)"
    )
    response_time: Optional[float] = Field(
        None, description="Response time in seconds (null if timeout/error)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-12-30T15:30:45.123456",
                "is_up": True,
                "status_code": 200,
                "response_time": 0.234,
            }
        }


class CurrentStatus(BaseModel):
    """Current status of a monitor.

    Represents the most recent status information for a monitor including
    whether it's up, the HTTP status code, response time, and timestamp.
    """

    is_up: Optional[bool] = Field(None, description="Current status")
    status_code: Optional[int] = Field(None, description="Current status code")
    response_time: Optional[float] = Field(None, description="Current response time")
    timestamp: Optional[str] = Field(None, description="Timestamp of latest check")

    class Config:
        json_schema_extra = {
            "example": {
                "is_up": True,
                "status_code": 200,
                "response_time": 0.234,
                "timestamp": "2025-12-30T15:30:45.123456",
            }
        }


class MonitorStatusDetail(BaseModel):
    """Detailed status information for a monitor.

    Includes the monitor's name, current status, and complete status
    history records over the requested time period.
    """

    name: str = Field(..., description="Monitor name")
    current_status: CurrentStatus = Field(..., description="Current status")
    history: List[StatusRecord] = Field(..., description="Status history records")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Google Search",
                "current_status": {
                    "is_up": True,
                    "status_code": 200,
                    "response_time": 0.234,
                    "timestamp": "2025-12-30T15:30:45.123456",
                },
                "history": [
                    {
                        "timestamp": "2025-12-30T15:30:45.123456",
                        "is_up": True,
                        "status_code": 200,
                        "response_time": 0.234,
                    },
                    {
                        "timestamp": "2025-12-30T15:29:45.123456",
                        "is_up": True,
                        "status_code": 200,
                        "response_time": 0.198,
                    },
                ],
            }
        }


class AllStatusResponse(BaseModel):
    """Response containing status for all monitors.

    Aggregated status information for all configured monitors, with response
    timestamp and detailed status for each monitor.
    """

    timestamp: str = Field(..., description="Response timestamp")
    monitors: List[MonitorStatusDetail] = Field(..., description="All monitors status")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-12-30T15:30:45.123456",
                "monitors": [
                    {
                        "name": "Google Search",
                        "current_status": {
                            "is_up": True,
                            "status_code": 200,
                            "response_time": 0.234,
                            "timestamp": "2025-12-30T15:30:45.123456",
                        },
                        "history": [
                            {
                                "timestamp": "2025-12-30T15:30:45.123456",
                                "is_up": True,
                                "status_code": 200,
                                "response_time": 0.234,
                            }
                        ],
                    }
                ],
            }
        }


class HealthResponse(BaseModel):
    """Health check response.

    Simple response indicating the health status of the API service.
    """

    status: str = Field(..., description="Health status")

    class Config:
        json_schema_extra = {"example": {"status": "ok"}}


class ConfigResponse(BaseModel):
    """Application configuration response.

    Contains the current application configuration settings including site title,
    degraded thresholds, and footer text.
    """

    configuration: dict = Field(..., description="Application configuration")

    class Config:
        json_schema_extra = {
            "example": {
                "configuration": {
                    "siteTitle": "Project 甘い",
                    "degraded_threshold": 200,
                    "footerText": "Copyright 2019-2025 © Rystal. All Rights Reserved.",
                }
            }
        }
