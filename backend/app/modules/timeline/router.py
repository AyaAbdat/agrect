from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentFarm, Db
from app.modules.timeline.schemas import TimelineOut
from app.modules.timeline.service import timeline

farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["timeline"])


@farm_router.get("/timeline", response_model=TimelineOut)
def get_timeline(
    farm: CurrentFarm,
    db: Db,
    date_from: Annotated[Date | None, Query(alias="from")] = None,
    date_to: Annotated[Date | None, Query(alias="to")] = None,
) -> TimelineOut:
    return timeline(db, farm, date_from, date_to)
