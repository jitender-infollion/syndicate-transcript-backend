IMAGE := syndicate-backend
CONTAINER := syndicate-backend
# Absolute path so `docker run --env-file` resolves it regardless of where docker's
# working dir ends up (a relative `.env.dev` intermittently failed with "no such file").
ENV_FILE := $(CURDIR)/.env.dev
ENV_FILE_PROD := $(CURDIR)/.env.production

.PHONY: build run-dev run-prod stop logs check-env check-env-prod

build:
	docker build --build-arg CACHEBUST=$$(date +%s) -t $(IMAGE) .

# Fail early with a clear message (instead of docker's confusing "open .env.dev:
# no such file") if the env file is missing.
check-env:
	@test -f "$(ENV_FILE)" || { echo "ERROR: env file not found: $(ENV_FILE)"; exit 1; }

check-env-prod:
	@test -f "$(ENV_FILE_PROD)" || { echo "ERROR: env file not found: $(ENV_FILE_PROD)"; exit 1; }

# One command: verify env -> rebuild image -> replace container -> run.
# Rebuilds first every time: code changes on disk only take effect in a fresh
# container, never in one that's already running (the image is a snapshot, not a
# live mount of src/). A cached build still picks up src changes automatically.
run-dev: check-env build stop
	docker run -d --name $(CONTAINER) -p 8000:8000 --env-file "$(ENV_FILE)" $(IMAGE)
	@echo ""
	@echo ">> $(CONTAINER) started on http://localhost:8000  —  follow logs with: make logs"

run-prod: check-env-prod build stop
	docker run -d --name $(CONTAINER) -p 8000:8000 --env-file "$(ENV_FILE_PROD)" $(IMAGE)
	@echo ""
	@echo ">> $(CONTAINER) (prod) started on http://localhost:8000  —  follow logs with: make logs"

stop:
	docker stop $(CONTAINER) 2>/dev/null || true
	docker rm $(CONTAINER) 2>/dev/null || true

logs:
	docker logs -f $(CONTAINER)
