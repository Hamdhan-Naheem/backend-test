from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EventDateCreate(BaseModel):
    date_time: datetime


class EventDateResponse(BaseModel):
    id: str
    event_id: str
    date_time: datetime

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    image_url: Optional[str] = None
    featured: bool = False
    dates: list[EventDateCreate] = []


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    image_url: Optional[str] = None
    featured: Optional[bool] = None
    dates: Optional[list[EventDateCreate]] = None


class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    image_url: Optional[str] = None
    featured: bool
    created_at: datetime
    updated_at: datetime
    dates: list[EventDateResponse] = []

    class Config:
        from_attributes = True
