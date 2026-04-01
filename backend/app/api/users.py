"""User auth routes: register, login, profile, follows."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token, get_current_user, hash_password, verify_password,
)
from ..database import get_db
from ..models import User, UserFollow, Event
from ..schemas import (
    FollowOut, LoginRequest, MessageResponse, RegisterRequest,
    TokenResponse, UserOut,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "Username already exists")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, "Email already exists")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
    return TokenResponse(access_token=token, role=user.role, username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")

    token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
    return TokenResponse(access_token=token, role=user.role, username=user.username)


@router.get("/me", response_model=UserOut)
def get_me(user=Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.query(User).get(int(user["user_id"]))
    if not u:
        raise HTTPException(404, "User not found")
    return u


@router.post("/follow/{event_id}", response_model=MessageResponse)
def follow_event(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = int(user["user_id"])
    exists = db.query(UserFollow).filter_by(user_id=uid, event_id=event_id).first()
    if exists:
        return MessageResponse(message="Already following")
    db.add(UserFollow(user_id=uid, event_id=event_id))
    db.commit()
    return MessageResponse(message="Followed")


@router.delete("/follow/{event_id}", response_model=MessageResponse)
def unfollow_event(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = int(user["user_id"])
    row = db.query(UserFollow).filter_by(user_id=uid, event_id=event_id).first()
    if row:
        db.delete(row)
        db.commit()
    return MessageResponse(message="Unfollowed")


@router.get("/follows", response_model=list[FollowOut])
def my_follows(user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = int(user["user_id"])
    rows = (
        db.query(UserFollow, Event)
        .join(Event, UserFollow.event_id == Event.id)
        .filter(UserFollow.user_id == uid)
        .order_by(UserFollow.created_at.desc())
        .all()
    )
    return [
        FollowOut(
            event_id=e.id,
            event_title=e.title,
            event_status=e.status,
            followed_at=f.created_at,
        )
        for f, e in rows
    ]


@router.get("/recommendations", response_model=list[int])
def recommendations(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Recommend events based on followed event categories."""
    uid = int(user["user_id"])
    followed_categories = (
        db.query(Event.category)
        .join(UserFollow, UserFollow.event_id == Event.id)
        .filter(UserFollow.user_id == uid)
        .distinct()
        .all()
    )
    cats = [c[0] for c in followed_categories if c[0]]

    followed_ids = (
        db.query(UserFollow.event_id).filter(UserFollow.user_id == uid).subquery()
    )

    q = db.query(Event).filter(Event.status == "active")
    if cats:
        q = q.filter(Event.category.in_(cats))
    q = q.filter(~Event.id.in_(db.query(UserFollow.event_id).filter(UserFollow.user_id == uid)))
    q = q.order_by(Event.importance.desc(), Event.updated_at.desc()).limit(10)

    return [e.id for e in q.all()]
