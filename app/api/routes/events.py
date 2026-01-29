from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from database import prisma
from schemas.event import (
    EventCreate,
    EventUpdate,
    EventResponse,
    EventDateResponse,
)
from api.deps import get_current_user

router = APIRouter(tags=["events"])


def _event_to_response(event) -> EventResponse:
    dates = []
    for d in getattr(event, "dates", []) or []:
        dt = getattr(d, "date_time", None) or getattr(d, "dateTime", None)
        if dt is not None:
            dates.append(
                EventDateResponse(
                    id=d.id,
                    event_id=getattr(d, "event_id", None) or getattr(d, "eventId", ""),
                    date_time=dt,
                )
            )
    return EventResponse(
        id=event.id,
        title=event.title,
        description=getattr(event, "description", None),
        location=getattr(event, "location", None),
        image_url=getattr(event, "image_url", None) or getattr(event, "imageUrl", None),
        featured=getattr(event, "featured", False),
        created_at=getattr(event, "created_at", event.createdAt),
        updated_at=getattr(event, "updated_at", event.updatedAt),
        dates=dates,
    )


@router.get("", response_model=list[EventResponse])
async def list_events(
    skip: int = 0,
    take: int = 20,
    featured: bool | None = None,
    sort: str = "date",
):
    where = {}
    if featured is not None:
        where["featured"] = featured

    events = await prisma.event.find_many(
        where=where,
        skip=skip,
        take=take,
        include={"dates": True},
    )

    if sort == "date":
        def earliest(e):
            dts = getattr(e, "dates", []) or []
            if dts:
                return min(
                    getattr(d, "date_time", None) or getattr(d, "dateTime", datetime.max)
                    for d in dts
                )
            return datetime.max

        events = sorted(events, key=earliest)

    return [_event_to_response(e) for e in events]


@router.get("/featured", response_model=list[EventResponse])
async def list_featured(take: int = 5):
    events = await prisma.event.find_many(
        where={"featured": True},
        take=take,
        include={"dates": True},
    )
    def earliest(e):
        dts = getattr(e, "dates", []) or []
        if dts:
            return min(
                getattr(d, "date_time", None) or getattr(d, "dateTime", datetime.max)
                for d in dts
            )
        return datetime.max
    events = sorted(events, key=earliest)
    return [_event_to_response(e) for e in events]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: str):
    event = await prisma.event.find_unique(
        where={"id": event_id},
        include={"dates": True},
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_response(event)


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    current_user: Annotated[object, Depends(get_current_user)],
):
    date_times = [d.date_time for d in body.dates]
    event = await prisma.event.create(
        data={
            "title": body.title,
            "description": body.description,
            "location": body.location,
            "imageUrl": body.image_url,
            "featured": body.featured,
            "dates": {
                "create": [{"dateTime": dt} for dt in date_times],
            },
        }
    )
    out = await prisma.event.find_unique(
        where={"id": event.id},
        include={"dates": True},
    )
    return _event_to_response(out)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    body: EventUpdate,
    current_user: Annotated[object, Depends(get_current_user)],
):
    existing = await prisma.event.find_unique(where={"id": event_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    data = body.model_dump(exclude_unset=True)
    dates = data.pop("dates", None)

    # Map snake_case to Prisma camelCase for DB
    if "image_url" in data:
        data["imageUrl"] = data.pop("image_url")
    if "created_at" in data:
        data.pop("created_at")
    if "updated_at" in data:
        data.pop("updated_at")

    if dates is not None:
        await prisma.eventdate.delete_many(where={"eventId": event_id})
        data["dates"] = {
            "create": [{"dateTime": d["date_time"]} for d in dates],
        }

    await prisma.event.update(where={"id": event_id}, data=data)
    out = await prisma.event.find_unique(
        where={"id": event_id},
        include={"dates": True},
    )
    return _event_to_response(out)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    current_user: Annotated[object, Depends(get_current_user)],
):
    """Delete an event (protected)."""
    existing = await prisma.event.find_unique(where={"id": event_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    await prisma.event.delete(where={"id": event_id})
