"""全局看板（§5）：实时查库计算。"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import DashboardOut
from ..services.ebbinghaus import dashboard_stats, select_queue

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tomorrow = date.today() + timedelta(days=1)
    review, new_words = select_queue(db, user.id, tomorrow)
    stats = dashboard_stats(db, user.id, next_review_count=len(review) + len(new_words))
    return DashboardOut(**stats)
