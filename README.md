# Tasks — a pleasant to-do app

A full-stack to-do application:

- **Backend** — FastAPI + SQLAlchemy + SQLite (stored in a Docker volume)
- **Frontend** — Vue 3 (Vite) with a polished light/dark theme
- **Serving** — nginx serves the built frontend and proxies `/api` to the API, all orchestrated with Docker Compose

## Features

- **Accounts** — sign up and sign in with email + password. Passwords are hashed with bcrypt; sessions use bearer tokens. Change your password from the account menu.
- **Email verification** — signing up sends a verification link. It's *soft*: you can use the app right away, but an unverified account shows a banner with a **Resend** button until you confirm your address.
- **Forgot password** — the sign-in screen has a *Forgot password?* link. We email a single-use reset link (valid for 1 hour); setting a new password signs you out everywhere else.
- **Personal & shared lists** — every list is either **personal** (only you) or **shared**. Shared lists appear for their members, who can all see and edit the tasks. Add people by email (they need a Tasks account).
- **Assign tasks to others** — in a shared list, assign a task by typing a member's **name or email** in the task's edit form (matching members appear in a dropdown with their name and email); the assignee shows as a chip on the task row. The list owner controls assignments; members can only assign tasks to themselves (and release their own). An **Assigned to me** view in the sidebar gathers everything assigned to you across every list.
- **Lists / projects** — keep separate lists in the sidebar; create, rename (double-click), and delete them. Each list gets its own color and task count.
- **Due dates** — set a due date when adding or editing a task. Chips show *Today*, *Tomorrow*, *Nov 21*, or *3d overdue*.
- **Drag-and-drop sorting** — reorder tasks by dragging (a glowing line shows the drop point). Drag a task onto a different list in the sidebar to move it there.
- **Filters** — All / Ongoing / Late / Done, with live counts.
- **Alerts** — a bell in the header shows a badge for overdue and due-today tasks; the panel lists Overdue, Due today, and Coming up. Clicking an alert jumps to its list and highlights the task. A toast warns you on load when something needs attention.
- **Late detection** — overdue tasks get red chips; tasks finished after their deadline get a *"finished late"* tag (completion time is tracked).
- Add, rename (double-click or ✏️), complete, and delete tasks
- Priorities (low / medium / high) with color-coded badges
- Clear completed (per list)
- Light + dark theme, remembered across visits, follows OS preference by default
- Skeleton loading, empty states, error banner, smooth animations, toasts

> Drag-and-drop uses the HTML5 drag API, so it works on desktop browsers. On touch devices use the edit menu to move/change tasks instead.

## Accounts and sharing

- On first boot the backend seeds a starter account so your existing data keeps working:
  **`you@example.com` / `changeme123`** (override with the `STARTER_EMAIL` / `STARTER_PASSWORD` environment variables in `docker-compose.yml`).
- Sign in with it, or create your own account from the **Create account** tab. Change the password from the avatar menu.
- **Personal lists** are private. **Shared lists** can be shared from the 👥 / ⚙️ button on a list: flip *Shared list* on, then invite people by email. Invitees must already have a Tasks account (ask them to sign up with that email first). Members can add, edit, and complete tasks; the owner can also rename, delete, and manage members.
- **Assignments** are made in a task's edit form by typing a member's **name or email** — a dropdown suggests matching members (name + email); leave it blank to unassign. The person must already be a member of the list — share the list with them first, there's no auto-invite. The **owner** can assign to any member, while **members** can only assign tasks to themselves and release their own. When someone is removed from a list (or sharing is turned off), their tasks are automatically unassigned, and a task moved to a list where its assignee isn't a member is unassigned too.

## Email: verification & password reset

Outgoing mail is sent over SMTP. In development a **Mailpit** container catches every message so nothing leaves your machine:

- Web inbox: **http://localhost:8025** — open it to read the verification and reset emails and click the links.
- SMTP endpoint: `mailpit:1025` (no TLS, no auth).

Configure delivery with environment variables on the `backend` service (all optional):

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `SMTP_HOST` | *(unset)* | SMTP server. **If unset, the email is written to the backend log instead.** |
| `SMTP_PORT` | `1025` | SMTP port |
| `SMTP_USER` / `SMTP_PASSWORD` | *(unset)* | Credentials, if the server needs them |
| `SMTP_STARTTLS` | `false` | Set to `1`/`true` to upgrade the connection with STARTTLS |
| `SMTP_FROM` | `Tasks <no-reply@tasks.local>` | From address |
| `APP_BASE_URL` | `http://localhost:8080` | Base URL used to build the links inside emails |

To use a real provider (Gmail, SendGrid, …), point `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD` at it and set `APP_BASE_URL` to your public URL.

Verification is **soft** — accounts work before they're verified, they just see a banner. Reset links are single-use and expire after 1 hour; the reset also marks the email verified and invalidates existing sessions. Existing accounts from before this feature are treated as verified so nobody is locked out.

## Run with Docker (recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build
```

- App: http://localhost:8080
- API docs (Swagger UI): http://localhost:8000/docs
- Mail inbox (Mailpit): http://localhost:8025

To stop: `docker compose down` (add `-v` to also delete the database volume).

The backend upgrades older databases in place (adds `projects`, due dates, positions, accounts, …), so existing tasks are preserved and moved to the seeded *Personal* list.

## Local development (without Docker)

Backend (needs Python 3.12+):

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (needs Node 20+), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173 — the Vite dev server proxies `/api` to the backend.

## API overview

All `/api/todos` and `/api/projects` endpoints require an `Authorization: Bearer <token>` header. The `register`, `login`, `verify`, `forgot-password` and `reset-password` endpoints are public.

| Method   | Path                             | Description                                        |
| -------- | -------------------------------- | -------------------------------------------------- |
| `POST`   | `/api/auth/register`             | Create an account (sends a verification email) → `{ token, user }` |
| `POST`   | `/api/auth/login`                | Sign in → `{ token, user }`                        |
| `POST`   | `/api/auth/logout`               | Invalidate the current token                       |
| `GET`    | `/api/auth/me`                   | The signed-in user                                 |
| `POST`   | `/api/auth/password`             | Change password                                    |
| `POST`   | `/api/auth/verify`               | Confirm an email address (`{ "token": … }`)        |
| `POST`   | `/api/auth/verify/resend`        | Re-send the verification email (signed in)         |
| `POST`   | `/api/auth/forgot-password`      | Email a reset link (`{ "email": … }`) → always 202 |
| `POST`   | `/api/auth/reset-password`       | Set a new password (`{ "token": …, "new_password": … }`) |
| `GET`    | `/api/projects`                  | List your lists + lists shared with you            |
| `POST`   | `/api/projects`                  | Create a list (`name`, `color`, `is_shared`)       |
| `PATCH`  | `/api/projects/{id}`             | Rename / recolor / toggle sharing (owner)          |
| `DELETE` | `/api/projects/{id}`             | Delete a list and its todos (owner)                |
| `GET`    | `/api/projects/{id}/members`     | List members of a shared list                      |
| `POST`   | `/api/projects/{id}/members`     | Invite by email (owner, `{ "email": … }`)          |
| `DELETE` | `/api/projects/{id}/members/{uid}` | Remove a member, or leave a list                 |
| `GET`    | `/api/todos`                     | List todos (`?project_id=`, `?filter=all\|ongoing\|completed\|late`) |
| `POST`   | `/api/todos`                     | Create a todo (title, priority, project, due date, `assignee_id` / `assignee_email`) |
| `PATCH`  | `/api/todos/{id}`                | Update title / completed / priority / due / project / `assignee_id` / `assignee_email` |
| `POST`   | `/api/todos/reorder`             | Save a new order (`{ "ids": [3, 1, 2] }`)          |
| `DELETE` | `/api/todos/{id}`                | Delete a todo                                      |
| `DELETE` | `/api/todos`                     | Delete completed todos (`?project_id=`)            |
| `GET`    | `/api/stats`                     | Task-accomplishments analysis (`?project_id=` optional): totals, completion rate, on-time vs late, per-priority/per-list breakdowns, and a 7-day trend |
| `GET`    | `/api/health`                    | Health check                                       |

## Project structure

```
├── docker-compose.yml      # Orchestration (backend + frontend + Mailpit + volume)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py         # FastAPI routes (auth, verify/reset, lists, sharing, todos)
│       ├── database.py     # Engine + session (SQLite via env var)
│       ├── models.py       # User, AuthSession, EmailToken, Project, ProjectMember, Todo
│       ├── schemas.py      # Pydantic request/response schemas
│       ├── security.py     # Password hashing, bearer-token auth, email-token helpers
│       ├── mailer.py       # SMTP sending (console fallback) + email templates
│       └── migrate.py      # In-place SQLite upgrades for old databases
└── frontend/
    ├── Dockerfile          # Build with Node, serve with nginx
    ├── nginx.conf          # Static files + /api proxy
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.js
        ├── App.vue         # Layout, state, drag & drop, alerts, auth gate, ?verify/?reset links
        ├── api.js          # Fetch-based API client (adds the auth header)
        ├── dateUtils.js    # Due-date math in the user's local timezone
        ├── style.css       # Theme tokens + all styling
        ├── composables/    # useTheme.js, useAuth.js
        └── components/     # AuthView (sign in/up/forgot/reset), VerifyBanner,
                           # UserMenu, ShareDialog, ProjectSidebar, AlertsBell,
                           # TodoInput, TodoFilters, TodoItem, ThemeToggle
```
