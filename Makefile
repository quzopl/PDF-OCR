.PHONY: install dev backend frontend test test-backend test-frontend test-e2e clean

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev:
	@echo "Starting backend on :8114 and frontend on :3101"
	@trap 'kill 0' INT; \
	  (cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8114 --reload 2>&1 | sed 's/^/[api] /') & \
	  (cd frontend && pnpm dev -p 3101 2>&1 | sed 's/^/[web] /') & \
	  wait

backend:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8114 --reload

frontend:
	cd frontend && pnpm dev -p 3101

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest -q

test-frontend:
	cd frontend && pnpm test

test-e2e:
	cd frontend && pnpm exec playwright test

clean:
	rm -rf /tmp/ocrapp backend/.pytest_cache backend/.ruff_cache backend/.venv \
	  frontend/node_modules frontend/.next
