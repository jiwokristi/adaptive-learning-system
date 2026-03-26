.PHONY: dev setup db backend frontend stop migrate seed

# First-time setup
setup: db
	cd backend && pip install -e ".[dev]" && cp -n ../.env.example .env 2>/dev/null || true
	cd frontend && npm install
	@echo ""
	@echo "Done! Edit backend/.env with your ANTHROPIC_API_KEY, then run: make migrate && make dev"

# Start everything
dev: db
	@trap 'kill 0' EXIT; \
	cd backend && uvicorn app.main:app --reload --port 8000 & \
	cd frontend && npm run dev & \
	wait

# Individual services
db:
	@docker compose up -d --wait

backend: db
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

# Database
migrate: db
	cd backend && alembic upgrade head

# Stop everything
stop:
	docker compose down

# Create a test user (MVP hardcoded ID)
seed: db
	cd backend && python seed.py
