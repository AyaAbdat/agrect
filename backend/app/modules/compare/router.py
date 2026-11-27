from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentFarm, Db
from app.modules.compare.schemas import CompareMetric, CompareOut
from app.modules.compare.service import compare

farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["compare"])


@farm_router.get("/compare", response_model=CompareOut)
def get_compare(
    farm: CurrentFarm,
    db: Db,
    metric: Annotated[CompareMetric, Query()],
    date: Annotated[Date | None, Query()] = None,
) -> CompareOut:
    return compare(db, farm, metric, date)
