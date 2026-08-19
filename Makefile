IMAGE := syndicate-backend
CONTAINER := syndicate-backend

.PHONY: build run-dev run-prod stop logs

build:
	docker build -t $(IMAGE) .

# Rebuilds first every time - code changes on disk only take effect in a
# fresh container, never in one that's already running (bit us more than
# once - the image is a snapshot, not a live mount of src/).
run-dev: build stop
	docker run -d --name $(CONTAINER) -p 8000:8000 --env-file .env.dev $(IMAGE)

run-prod: build stop
	docker run -d --name $(CONTAINER) -p 8000:8000 --env-file .env.production $(IMAGE)

stop:
	docker stop $(CONTAINER) 2>/dev/null || true
	docker rm $(CONTAINER) 2>/dev/null || true

logs:
	docker logs -f $(CONTAINER)
