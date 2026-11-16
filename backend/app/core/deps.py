import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import get_current_user
from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm
from app.modules.registry.models import Block

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[AppUser, Depends(get_current_user)]


def get_current_farm(farm_id: uuid.UUID, db: Db, user: CurrentUser) -> Farm:
    farm = db.get(Farm, farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("farm.not_found", 404)
    return farm


CurrentFarm = Annotated[Farm, Depends(get_current_farm)]


def get_current_block(block_id: uuid.UUID, db: Db, user: CurrentUser) -> Block:
    block = db.get(Block, block_id)
    if block is None or block.farm.owner_user_id != user.id:
        raise AppError("block.not_found", 404)
    return block


CurrentBlock = Annotated[Block, Depends(get_current_block)]
