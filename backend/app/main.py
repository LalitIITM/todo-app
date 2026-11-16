import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, SessionLocal, engine, get_db
from .mailer import send_password_reset_email, send_verification_email
from .migrate import ensure_schema
from .security import (
    RESET_LIFETIME,
    RESET_PURPOSE,
    VERIFY_LIFETIME,
    VERIFY_PURPOSE,
    create_session,
    get_current_user,
    hash_password,
    issue_email_token,
    load_email_token,
    verify_password,
)

TODO_NOT_FOUND = "Todo not found"
PROJECT_NOT_FOUND = "Project not found"
NO_PROJECTS = "Create a list first"
NOT_OWNER = "Only the list owner can do that"
NOT_MEMBER = "That person isn't a member of this list"
CANNOT_ASSIGN = "Only the list owner can assign tasks to others"
NO_ACCOUNT = "No account found with that email"
SHARE_FIRST = "Share this list with them first"

DEFAULT_PROJECT_NAME = "Personal"
DEFAULT_PROJECT_COLOR = "#6366f1"
PROJECT_COLORS = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e", "#a855f7"]

# Seeded on first boot so an existing database keeps its data.
STARTER_EMAIL = os.getenv("STARTER_EMAIL", "you@example.com")
STARTER_PASSWORD = os.getenv("STARTER_PASSWORD", "changeme123")
STARTER_NAME = os.getenv("STARTER_NAME", "You")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables, upgrade older databases, make sure an account + list exist.
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    seed_starter_account()
    yield


# ---------- helpers ----------


def accessible_projects(db: Session, user: models.User) -> list[models.Project]:
    """Every list the user can see: their own plus shared lists they belong to."""
    member_of = (
        select(models.ProjectMember.project_id)
        .join(models.Project, models.Project.id == models.ProjectMember.project_id)
        .where(
            models.ProjectMember.user_id == user.id,
            models.Project.is_shared.is_(True),
        )
    )
    return list(
        db.scalars(
            select(models.Project)
            .where(
                or_(
                    models.Project.owner_id == user.id,
                    models.Project.id.in_(member_of),
                )
            )
            .order_by(models.Project.position, models.Project.id)
        )
    )


def ensure_default_project(db: Session, user: models.User) -> models.Project:
    project = db.scalars(
        select(models.Project)
        .where(models.Project.owner_id == user.id)
        .order_by(models.Project.position, models.Project.id)
    ).first()
    if project is None:
        project = models.Project(
            name=DEFAULT_PROJECT_NAME,
            color=DEFAULT_PROJECT_COLOR,
            position=0,
            owner_id=user.id,
            is_shared=False,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
    return project


def seed_starter_account() -> None:
    with SessionLocal() as db:
        user = db.scalars(select(models.User).order_by(models.User.id)).first()
        if user is None:
            user = models.User(
                email=STARTER_EMAIL,
                name=STARTER_NAME,
                password_hash=hash_password(STARTER_PASSWORD),
                # The seeded account has no real inbox, so treat it as verified.
                email_verified=True,
                email_verified_at=models.utcnow(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Adopt lists and tasks from pre-accounts databases.
        orphans = list(
            db.scalars(select(models.Project).where(models.Project.owner_id.is_(None)))
        )
        for project in orphans:
            project.owner_id = user.id
        if orphans:
            db.commit()

        stray = db.scalar(
            select(func.count())
            .select_from(models.Todo)
            .where(models.Todo.project_id.is_(None))
        )
        if stray:
            db.execute(
                update(models.Todo)
                .where(models.Todo.project_id.is_(None))
                .values(project_id=ensure_default_project(db, user).id)
            )
            db.commit()

        ensure_default_project(db, user)


def user_can_access(db: Session, project: models.Project, user: models.User) -> bool:
    if project.owner_id == user.id:
        return True
    if not project.is_shared:
        return False
    return (
        db.scalar(
            select(models.ProjectMember.id).where(
                models.ProjectMember.project_id == project.id,
                models.ProjectMember.user_id == user.id,
            )
        )
        is not None
    )


def require_project(db: Session, user: models.User, project_id: int) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None or not user_can_access(db, project, user):
        # Don't leak the existence of other people's lists.
        raise HTTPException(status_code=404, detail=PROJECT_NOT_FOUND)
    return project


def require_owned_project(
    db: Session, user: models.User, project_id: int
) -> models.Project:
    project = require_project(db, user, project_id)
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail=NOT_OWNER)
    return project


def project_to_out(project: models.Project) -> schemas.ProjectOut:
    owner = None
    if project.owner is not None:
        owner = schemas.MemberOut(
            user_id=project.owner.id,
            email=project.owner.email,
            name=project.owner.name,
        )
    return schemas.ProjectOut(
        id=project.id,
        name=project.name,
        color=project.color,
        position=project.position,
        is_shared=project.is_shared,
        owner_id=project.owner_id,
        owner=owner,
        created_at=project.created_at,
        members=[
            schemas.MemberOut(
                user_id=member.user_id,
                email=member.user.email,
                name=member.user.name,
            )
            for member in sorted(project.members, key=lambda m: m.id)
        ],
    )


def project_member_ids(db: Session, project: models.Project) -> set[int]:
    """Everyone who may be assigned a task in this list (owner + members)."""
    ids = {member.user_id for member in project.members}
    if project.owner_id is not None:
        ids.add(project.owner_id)
    return ids


def find_user_by_email(db: Session, email: str) -> models.User | None:
    return db.scalar(
        select(models.User).where(
            func.lower(models.User.email) == email.strip().lower()
        )
    )


def resolve_assignee_email(
    db: Session, project: models.Project, email: str | None
) -> int | None:
    """Turn an assignee email into a user id, or None to unassign.

    The person must already have an account *and* be a member of this list —
    there's no auto-invite here; share the list with them first.
    """
    email = (email or "").strip()
    if not email:
        return None
    target = find_user_by_email(db, email)
    if target is None:
        raise HTTPException(status_code=400, detail=NO_ACCOUNT)
    if target.id not in project_member_ids(db, project):
        raise HTTPException(status_code=400, detail=SHARE_FIRST)
    return target.id


def todo_to_out(todo: models.Todo) -> schemas.TodoOut:
    assignee = None
    if todo.assignee is not None:
        assignee = schemas.MemberOut(
            user_id=todo.assignee.id,
            email=todo.assignee.email,
            name=todo.assignee.name,
        )
    return schemas.TodoOut(
        id=todo.id,
        title=todo.title,
        completed=todo.completed,
        priority=todo.priority,
        project_id=todo.project_id,
        due_date=todo.due_date,
        position=todo.position,
        created_at=todo.created_at,
        completed_at=todo.completed_at,
        assignee=assignee,
    )


def require_accessible_todo(
    db: Session, user: models.User, todo_id: int
) -> models.Todo:
    todo = db.get(models.Todo, todo_id)
    if todo is None or todo.project_id is None:
        raise HTTPException(status_code=404, detail=TODO_NOT_FOUND)
    require_project(db, user, todo.project_id)
    return todo


app = FastAPI(title="Tasks API", version="3.0.0", lifespan=lifespan)

# Allow the Vite dev server during local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------- Auth ----------


@app.post(
    "/api/auth/register",
    response_model=schemas.AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    exists = db.scalar(
        select(models.User).where(func.lower(models.User.email) == email)
    )
    if exists is not None:
        raise HTTPException(
            status_code=409, detail="An account with that email already exists"
        )

    user = models.User(
        email=email,
        name=payload.name.strip() if payload.name else None,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    ensure_default_project(db, user)

    # Fire off the verification email (soft: the account works meanwhile).
    token = issue_email_token(db, user, VERIFY_PURPOSE, VERIFY_LIFETIME)
    send_verification_email(user.email, token)

    session = create_session(db, user)
    return schemas.AuthResponse(token=session.token, user=user)


@app.post("/api/auth/login", response_model=schemas.AuthResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(
        select(models.User).where(func.lower(models.User.email) == email)
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    session = create_session(db, user)
    return schemas.AuthResponse(token=session.token, user=user)


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        session = db.scalar(
            select(models.AuthSession).where(models.AuthSession.token == token)
        )
        if session is not None:
            db.delete(session)
            db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/auth/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


@app.post("/api/auth/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: schemas.ChangePasswordRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Email verification ----------

INVALID_VERIFY = "This verification link is invalid or has expired"
INVALID_RESET = "This reset link is invalid or has expired"


@app.post("/api/auth/verify", response_model=schemas.UserOut)
def verify_email(payload: schemas.VerifyRequest, db: Session = Depends(get_db)):
    row = load_email_token(db, payload.token, VERIFY_PURPOSE)
    if row is None:
        raise HTTPException(status_code=400, detail=INVALID_VERIFY)

    user = db.get(models.User, row.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail=INVALID_VERIFY)

    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
    row.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/auth/verify/resend", response_model=schemas.MessageOut)
def resend_verification(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.email_verified:
        return schemas.MessageOut(detail="Your email is already verified")
    token = issue_email_token(db, user, VERIFY_PURPOSE, VERIFY_LIFETIME)
    send_verification_email(user.email, token)
    return schemas.MessageOut(detail="Verification email sent — check your inbox")


# ---------- Password reset ----------


@app.post(
    "/api/auth/forgot-password",
    response_model=schemas.MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)
):
    email = payload.email.strip().lower()
    user = db.scalar(
        select(models.User).where(func.lower(models.User.email) == email)
    )
    if user is not None:
        token = issue_email_token(db, user, RESET_PURPOSE, RESET_LIFETIME)
        send_password_reset_email(user.email, token)

    # Same answer either way, so we never reveal which emails have accounts.
    return schemas.MessageOut(
        detail="If that email has an account, a reset link is on its way"
    )


@app.post("/api/auth/reset-password", response_model=schemas.MessageOut)
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    row = load_email_token(db, payload.token, RESET_PURPOSE)
    if row is None:
        raise HTTPException(status_code=400, detail=INVALID_RESET)

    user = db.get(models.User, row.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail=INVALID_RESET)

    user.password_hash = hash_password(payload.new_password)
    # Proving control of the mailbox also verifies the address.
    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
    row.used_at = datetime.now(timezone.utc)
    # Existing sessions can't be trusted after a password reset.
    db.execute(
        delete(models.AuthSession).where(models.AuthSession.user_id == user.id)
    )
    db.commit()
    return schemas.MessageOut(detail="Password updated — you can sign in now")


# ---------- Projects (lists) ----------


@app.get("/api/projects", response_model=list[schemas.ProjectOut])
def list_projects(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [project_to_out(p) for p in accessible_projects(db, user)]


@app.post(
    "/api/projects",
    response_model=schemas.ProjectOut,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: schemas.ProjectCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    max_position = (
        db.scalar(
            select(func.max(models.Project.position)).where(
                models.Project.owner_id == user.id
            )
        )
        or 0
    )
    color = payload.color or PROJECT_COLORS[max_position % len(PROJECT_COLORS)]
    project = models.Project(
        name=payload.name,
        color=color,
        position=max_position + 1,
        owner_id=user.id,
        is_shared=payload.is_shared,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_to_out(project)


@app.patch("/api/projects/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: int,
    payload: schemas.ProjectUpdate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = require_owned_project(db, user, project_id)
    updates = payload.model_dump(exclude_unset=True)

    # Turning sharing off drops everyone who was added, and unassigns the
    # tasks that were assigned to them (the owner can stay assigned).
    if updates.get("is_shared") is False and project.is_shared:
        for member in list(project.members):
            db.delete(member)
        db.execute(
            update(models.Todo)
            .where(
                models.Todo.project_id == project.id,
                models.Todo.assignee_id.is_not(None),
                models.Todo.assignee_id != project.owner_id,
            )
            .values(assignee_id=None)
        )

    for field, value in updates.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project_to_out(project)


@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = require_owned_project(db, user, project_id)
    # The ORM relationship cascades and deletes the project's todos + members.
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Sharing (members) ----------


@app.get(
    "/api/projects/{project_id}/members",
    response_model=list[schemas.MemberOut],
)
def list_members(
    project_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = require_project(db, user, project_id)
    return project_to_out(project).members


@app.post(
    "/api/projects/{project_id}/members",
    response_model=schemas.ProjectOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    project_id: int,
    payload: schemas.MemberAdd,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = require_owned_project(db, user, project_id)
    if not project.is_shared:
        raise HTTPException(
            status_code=400, detail="Turn on sharing for this list first"
        )

    email = payload.email.strip().lower()
    target = db.scalar(
        select(models.User).where(func.lower(models.User.email) == email)
    )
    if target is None:
        raise HTTPException(status_code=404, detail=NO_ACCOUNT)
    if target.id == project.owner_id:
        raise HTTPException(
            status_code=400, detail="That person already owns this list"
        )

    already = db.scalar(
        select(models.ProjectMember).where(
            models.ProjectMember.project_id == project.id,
            models.ProjectMember.user_id == target.id,
        )
    )
    if already is None:
        db.add(models.ProjectMember(project_id=project.id, user_id=target.id))
        db.commit()
        db.refresh(project)

    return project_to_out(project)


@app.delete(
    "/api/projects/{project_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    project_id: int,
    member_user_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = require_project(db, user, project_id)
    # The owner can remove anyone; a member can remove (leave) themselves.
    if project.owner_id != user.id and member_user_id != user.id:
        raise HTTPException(status_code=403, detail=NOT_OWNER)

    member = db.scalar(
        select(models.ProjectMember).where(
            models.ProjectMember.project_id == project.id,
            models.ProjectMember.user_id == member_user_id,
        )
    )
    if member is not None:
        db.delete(member)
        # Their tasks go back to the unassigned pool.
        db.execute(
            update(models.Todo)
            .where(
                models.Todo.project_id == project.id,
                models.Todo.assignee_id == member_user_id,
            )
            .values(assignee_id=None)
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Todos ----------


@app.get("/api/todos", response_model=list[schemas.TodoOut])
def list_todos(
    project_id: int | None = None,
    filter: str = Query("all", pattern="^(all|ongoing|completed|late)$"),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ids = [p.id for p in accessible_projects(db, user)]
    if project_id is not None:
        if project_id not in ids:
            return []
        ids = [project_id]
    if not ids:
        return []

    query = select(models.Todo).where(models.Todo.project_id.in_(ids))
    if filter == "ongoing":
        query = query.where(models.Todo.completed.is_(False))
    elif filter == "completed":
        query = query.where(models.Todo.completed.is_(True))
    elif filter == "late":
        query = query.where(
            models.Todo.completed.is_(False),
            models.Todo.due_date < date.today(),
        )
    query = query.order_by(models.Todo.project_id, models.Todo.position, models.Todo.id)
    return [todo_to_out(todo) for todo in db.scalars(query)]


@app.post(
    "/api/todos",
    response_model=schemas.TodoOut,
    status_code=status.HTTP_201_CREATED,
)
def create_todo(
    payload: schemas.TodoCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project_id = payload.project_id
    if project_id is None:
        projects = accessible_projects(db, user)
        if not projects:
            raise HTTPException(status_code=400, detail=NO_PROJECTS)
        project = projects[0]
        project_id = project.id
    else:
        project = require_project(db, user, project_id)

    # Assignee (if any) must be someone in this list; only the owner may
    # assign a task to somebody else. The UI sends an email address.
    assignee_id = payload.assignee_id
    if payload.assignee_email is not None:
        assignee_id = resolve_assignee_email(db, project, payload.assignee_email)
    if assignee_id is not None:
        if assignee_id not in project_member_ids(db, project):
            raise HTTPException(status_code=400, detail=NOT_MEMBER)
        if project.owner_id != user.id and assignee_id != user.id:
            raise HTTPException(status_code=403, detail=CANNOT_ASSIGN)

    # New tasks go to the top of their list.
    min_position = db.scalar(
        select(func.min(models.Todo.position)).where(
            models.Todo.project_id == project_id
        )
    )
    data = payload.model_dump(exclude={"project_id", "assignee_id", "assignee_email"})
    todo = models.Todo(
        **data,
        project_id=project_id,
        assignee_id=assignee_id,
        position=(min_position - 1) if min_position is not None else 0,
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo_to_out(todo)


@app.patch("/api/todos/{todo_id}", response_model=schemas.TodoOut)
def update_todo(
    todo_id: int,
    payload: schemas.TodoUpdate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    todo = require_accessible_todo(db, user, todo_id)
    updates = payload.model_dump(exclude_unset=True)

    # Track completion time so the UI can tell "finished late" tasks apart.
    if updates.get("completed") is True:
        todo.completed_at = datetime.now(timezone.utc)
    elif updates.get("completed") is False:
        todo.completed_at = None

    # Moving to another list: land at the top of the target list.
    target_project = updates.get("project_id")
    moving = target_project is not None and target_project != todo.project_id
    if moving:
        project = require_project(db, user, target_project)
        min_position = db.scalar(
            select(func.min(models.Todo.position)).where(
                models.Todo.project_id == target_project
            )
        )
        todo.position = (min_position - 1) if min_position is not None else 0
    else:
        project = require_project(db, user, todo.project_id)

    # The UI assigns by email; resolve it to a user id (or None to unassign).
    if "assignee_email" in updates:
        updates["assignee_id"] = resolve_assignee_email(
            db, project, updates.pop("assignee_email")
        )

    # Assignment rules: only members of the list are valid assignees, and
    # only the owner may hand a task to somebody else. A member can self-assign
    # an unassigned task (or one already theirs) and release their own task.
    if "assignee_id" in updates:
        new_assignee = updates["assignee_id"]
        if new_assignee is not None and new_assignee not in project_member_ids(
            db, project
        ):
            raise HTTPException(status_code=400, detail=NOT_MEMBER)
        if project.owner_id != user.id:
            may_change = todo.assignee_id in (None, user.id)
            if not may_change or new_assignee not in (None, user.id):
                raise HTTPException(status_code=403, detail=CANNOT_ASSIGN)
    elif moving and todo.assignee_id is not None:
        # The task changed lists — drop an assignee who isn't in the new list.
        if todo.assignee_id not in project_member_ids(db, project):
            updates["assignee_id"] = None

    for field, value in updates.items():
        setattr(todo, field, value)

    db.commit()
    db.refresh(todo)
    return todo_to_out(todo)


@app.post("/api/todos/reorder")
def reorder_todos(
    payload: schemas.ReorderRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    todos = []
    for todo_id in payload.ids:
        todos.append(require_accessible_todo(db, user, todo_id))
    for index, todo in enumerate(todos):
        todo.position = index
    db.commit()
    return {"ok": True, "count": len(todos)}


@app.delete("/api/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(
    todo_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    todo = require_accessible_todo(db, user, todo_id)
    db.delete(todo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.delete("/api/todos", status_code=status.HTTP_204_NO_CONTENT)
def clear_completed(
    project_id: int | None = None,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ids = [p.id for p in accessible_projects(db, user)]
    if project_id is not None:
        if project_id not in ids:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        ids = [project_id]
    if not ids:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    db.execute(
        delete(models.Todo).where(
            models.Todo.completed.is_(True),
            models.Todo.project_id.in_(ids),
        )
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Stats (task accomplishments) ----------


def _aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@app.get("/api/stats", response_model=schemas.StatsOut)
def task_stats(
    project_id: int | None = None,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyse the tasks the user can see: completion, timing, and trends."""
    projects = accessible_projects(db, user)
    if project_id is not None:
        projects = [p for p in projects if p.id == project_id]
    ids = [p.id for p in projects]

    todos = (
        list(db.scalars(select(models.Todo).where(models.Todo.project_id.in_(ids))))
        if ids
        else []
    )

    today = datetime.now(timezone.utc).date()
    week_ago = today - timedelta(days=6)

    completed = [t for t in todos if t.completed]
    open_todos = [t for t in todos if not t.completed]
    overdue = [t for t in open_todos if t.due_date is not None and t.due_date < today]

    def completed_on(todo: models.Todo) -> date | None:
        return _aware(todo.completed_at).date() if todo.completed_at else None

    on_time = 0
    late = 0
    durations: list[float] = []
    for todo in completed:
        done = completed_on(todo)
        if todo.due_date is not None and done is not None:
            if done <= todo.due_date:
                on_time += 1
            else:
                late += 1
        if todo.completed_at is not None:
            span = _aware(todo.completed_at) - _aware(todo.created_at)
            durations.append(span.total_seconds() / 86400)

    by_priority = [
        schemas.StatsBucket(
            label=level,
            total=sum(1 for t in todos if t.priority == level),
            completed=sum(1 for t in todos if t.priority == level and t.completed),
        )
        for level in ("high", "medium", "low")
    ]

    by_list = [
        schemas.StatsBucket(
            label=project.name,
            total=sum(1 for t in todos if t.project_id == project.id),
            completed=sum(
                1 for t in todos if t.project_id == project.id and t.completed
            ),
        )
        for project in projects
    ]

    last_7_days = []
    for offset in range(7):
        day = week_ago + timedelta(days=offset)
        last_7_days.append(
            schemas.StatsBucket(
                label=day.isoformat(),
                total=sum(
                    1
                    for t in todos
                    if t.created_at and _aware(t.created_at).date() == day
                ),
                completed=sum(1 for t in completed if completed_on(t) == day),
            )
        )

    # Current streak: consecutive days with at least one completion, counting
    # back from today. If nothing was completed today yet, the streak can still
    # be alive from yesterday.
    completion_days = {done for t in completed if (done := completed_on(t))}
    current_streak = 0
    cursor = today
    if cursor not in completion_days:
        cursor = today - timedelta(days=1)
    while cursor in completion_days:
        current_streak += 1
        cursor -= timedelta(days=1)

    # Group tasks by assignee (including an "Unassigned" group).
    groups: dict[int | None, list[models.Todo]] = {}
    for todo in todos:
        groups.setdefault(todo.assignee_id, []).append(todo)

    assignee_ids = [uid for uid in groups if uid is not None]
    people = (
        {
            u.id: u
            for u in db.scalars(
                select(models.User).where(models.User.id.in_(assignee_ids))
            )
        }
        if assignee_ids
        else {}
    )

    by_assignee = []
    for uid, group in groups.items():
        person = people.get(uid) if uid is not None else None
        if uid is None:
            label, email = "Unassigned", None
        elif person is not None:
            label, email = (person.name or person.email), person.email
        else:
            label, email = f"user {uid}", None
        by_assignee.append(
            schemas.AssigneeStats(
                user_id=uid,
                label=label,
                email=email,
                total=len(group),
                completed=sum(1 for t in group if t.completed),
            )
        )
    by_assignee.sort(key=lambda b: (-b.total, b.label.lower()))

    total = len(todos)
    return schemas.StatsOut(
        total=total,
        completed=len(completed),
        open=len(open_todos),
        overdue=len(overdue),
        completion_rate=(len(completed) / total) if total else 0.0,
        completed_today=sum(1 for t in completed if completed_on(t) == today),
        completed_this_week=sum(
            1
            for t in completed
            if (done := completed_on(t)) is not None and week_ago <= done <= today
        ),
        completed_on_time=on_time,
        completed_late=late,
        avg_completion_days=(sum(durations) / len(durations)) if durations else None,
        current_streak=current_streak,
        by_priority=by_priority,
        by_list=by_list,
        by_assignee=by_assignee,
        last_7_days=last_7_days,
    )
