# Makefile Guide

A Makefile lets you define shortcuts for common terminal commands. Instead of typing long commands, you just type `make <name>`.

---

## How Makefiles Work (30-second version)

```makefile
name: dependency
	command to run
```

- **name** — what you type after `make` (e.g., `make dev`)
- **dependency** — another command that runs first (e.g., `db` means "start the database before doing this")
- **command** — the actual shell command that runs

If a command has a dependency like `dev: db`, it means: "run `make db` first, then run the `dev` commands."

---

## Line-by-Line Breakdown

### `.PHONY`

```makefile
.PHONY: dev setup db backend frontend stop migrate seed
```

**What it does**: Tells Make that these names are commands, not files. Without this, if a file called `dev` existed in the folder, `make dev` would think "the file already exists, nothing to do" and skip it.

**Plain English**: "These are command names, not file names."

---

### `make setup`

```makefile
setup: db
	cd backend && pip install -e ".[dev]" && cp -n ../.env.example .env 2>/dev/null || true
	cd frontend && npm install
	@echo ""
	@echo "Done! Edit backend/.env with your ANTHROPIC_API_KEY, then run: make migrate && make dev"
```

**Dependency**: `db` — starts the database first (see below).

**Line by line**:

| Line | What it does | Plain English |
|------|-------------|---------------|
| `cd backend && pip install -e ".[dev]"` | Goes into the `backend/` folder and installs all Python dependencies | "Install the backend" |
| `cp -n ../.env.example .env` | Copies `.env.example` to `.env`, but only if `.env` doesn't already exist (`-n` = no-clobber) | "Create the config file from the template, don't overwrite if it already exists" |
| `2>/dev/null \|\| true` | Hides the error message if the copy fails, and doesn't crash the script | "If the copy fails, that's fine, keep going" |
| `cd frontend && npm install` | Goes into `frontend/` and installs JavaScript dependencies | "Install the frontend" |
| `@echo "Done!..."` | Prints a message. The `@` hides the command itself so you only see the output | "Print a helpful next-steps message" |

**When to run**: Once, when you first clone the project.

---

### `make dev`

```makefile
dev: db
	@trap 'kill 0' EXIT; \
	cd backend && uvicorn app.main:app --reload --port 8000 & \
	cd frontend && npm run dev & \
	wait
```

**Dependency**: `db` — makes sure the database is running.

**Line by line**:

| Line | What it does | Plain English |
|------|-------------|---------------|
| `@trap 'kill 0' EXIT` | When you press Ctrl+C, kill ALL background processes started by this command | "When I stop this, stop everything" |
| `cd backend && uvicorn app.main:app --reload --port 8000 &` | Starts the backend server on port 8000. The `&` runs it in the background | "Start the API server in the background" |
| `cd frontend && npm run dev &` | Starts the frontend dev server. Also backgrounded with `&` | "Start the website in the background" |
| `wait` | Keeps the command running until you press Ctrl+C | "Sit here and wait until I'm told to stop" |

The `\` at the end of each line means "this is all one command, continued on the next line."

**When to run**: Every time you want to work on the project.

---

### `make db`

```makefile
db:
	@docker compose up -d --wait
```

**What it does**: Starts the database using Docker.

**Breaking down the flags**:

| Flag | What it does | Plain English |
|------|-------------|---------------|
| `docker compose up` | Reads `docker-compose.yml` and starts the services defined in it (PostgreSQL + Redis) | "Start the database" |
| `-d` | "Detached" mode — runs in the background so you get your terminal back | "Run it in the background, don't take over my terminal" |
| `--wait` | Waits until the services are actually healthy before returning | "Don't say you're done until the database is actually ready" |

**Docker, dumbed down**: Docker is like a lightweight virtual machine. Instead of installing PostgreSQL on your actual computer (and dealing with version conflicts, config files, etc.), Docker runs it in an isolated container. `docker-compose.yml` is the recipe that says "I need PostgreSQL version 16 with the pgvector extension, running on port 5432." Docker downloads and runs it for you.

**When to run**: You don't usually run this directly — `make dev` calls it automatically.

---

### `make backend`

```makefile
backend: db
	cd backend && uvicorn app.main:app --reload --port 8000
```

**What it does**: Starts just the backend server (no frontend).

| Part | What it does | Plain English |
|------|-------------|---------------|
| `uvicorn` | A Python web server that runs FastAPI apps | "The thing that serves the API" |
| `app.main:app` | "In the file `app/main.py`, use the variable called `app`" | "Run this specific application" |
| `--reload` | Automatically restarts when you edit code | "Watch for file changes and restart" |
| `--port 8000` | Listen on port 8000 (so you access it at `http://localhost:8000`) | "Use port 8000" |

**When to run**: When you only want to work on the backend.

---

### `make frontend`

```makefile
frontend:
	cd frontend && npm run dev
```

**What it does**: Starts just the Next.js dev server (no backend).

**When to run**: When you only want to work on the frontend.

---

### `make migrate`

```makefile
migrate: db
	cd backend && alembic upgrade head
```

**What it does**: Creates/updates the database tables.

| Part | What it does | Plain English |
|------|-------------|---------------|
| `alembic` | A database migration tool — it tracks what changes need to be made to the database schema | "The database table manager" |
| `upgrade head` | Apply all pending migrations (table creations, column changes, etc.) up to the latest version | "Make the database match the latest code" |

**Migration, dumbed down**: Your code defines tables (users, documents, concepts, etc.). Alembic translates those definitions into SQL commands (`CREATE TABLE ...`) and runs them. It also tracks which migrations have already been applied so it doesn't run them twice.

**When to run**: Once after `make setup`, and again whenever someone adds new database tables or columns.

---

### `make stop`

```makefile
stop:
	docker compose down
```

**What it does**: Stops the database containers.

| Part | What it does | Plain English |
|------|-------------|---------------|
| `docker compose down` | Stops and removes the containers defined in `docker-compose.yml` | "Shut down the database" |

Note: Your data is preserved in a Docker volume (`pgdata`). Stopping containers doesn't delete your data.

**When to run**: When you're done working and want to free up resources.

---

### `make seed`

```makefile
seed: db
	cd backend && python seed.py
```

**What it does**: Runs `backend/seed.py`, which creates a test user in the database with a hardcoded ID. The frontend uses this ID since we don't have authentication yet.

**When to run**: Once, after `make migrate`.

---

## Typical Workflow

```bash
# Day 1 (first time)
make setup          # install everything
# Edit backend/.env → add your ANTHROPIC_API_KEY
make migrate        # create database tables
make seed           # create test user
make dev            # start working

# Day 2+ (every other time)
make dev            # that's it

# Done for the day
# Ctrl+C to stop the servers
make stop           # optional: shut down the database too
```
