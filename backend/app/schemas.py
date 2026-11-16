from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Priority = Literal["low", "medium", "high"]


# ---------- Auth ----------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None
    email_verified: bool


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class VerifyRequest(BaseModel):
    token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class MessageOut(BaseModel):
    detail: str


# ---------- Projects ----------


class MemberOut(BaseModel):
    user_id: int
    email: str
    name: str | None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    is_shared: bool = False


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    is_shared: bool | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    color: str
    position: int
    is_shared: bool
    owner_id: int | None
    owner: MemberOut | None = None
    created_at: datetime
    members: list[MemberOut] = []


class MemberAdd(BaseModel):
    email: EmailStr


# ---------- Todos ----------


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: Priority = "medium"
    project_id: int | None = None
    due_date: date | None = None
    assignee_id: int | None = None
    assignee_email: str | None = None


class TodoUpdate(BaseModel):
    """All fields optional — only the ones sent are updated.

    Send `due_date: null` to clear a due date.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    completed: bool | None = None
    priority: Priority | None = None
    project_id: int | None = None
    due_date: date | None = None
    assignee_id: int | None = None
    # Assign by email instead of id (the app uses this). Must be a member.
    assignee_email: str | None = None


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    completed: bool
    priority: Priority
    project_id: int | None
    due_date: date | None
    position: int
    created_at: datetime
    completed_at: datetime | None
    assignee: MemberOut | None = None


class ReorderRequest(BaseModel):
    """Ordered todo ids; each gets `position` = its index."""

    ids: list[int] = Field(min_length=1)


# ---------- Stats (task accomplishments) ----------


class StatsBucket(BaseModel):
    """A labelled slice of tasks (e.g. one list, one priority, one day)."""

    label: str
    total: int
    completed: int


class StatsOut(BaseModel):
    """An analysis of the tasks the signed-in user can see."""

    total: int
    completed: int
    open: int
    overdue: int
    completion_rate: float  # completed / total, 0.0–1.0
    completed_today: int
    completed_this_week: int
    completed_on_time: int
    completed_late: int
    avg_completion_days: float | None  # None when nothing is completed yet
    by_priority: list[StatsBucket]
    by_list: list[StatsBucket]
    last_7_days: list[StatsBucket]  # oldest → newest, ending today
