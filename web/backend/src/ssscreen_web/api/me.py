from fastapi import APIRouter, Depends

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.api.schemas import MeResponse
from ssscreen_web.infrastructure.models import User

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
