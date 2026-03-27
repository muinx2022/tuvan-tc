#!/usr/bin/env bash
set -euo pipefail

COMMIT_SHA="${1:-unknown}"
shift || true

if [[ $# -eq 0 ]]; then
  echo "No services requested. Nothing to deploy."
  exit 0
fi

if [[ -z "${DEPLOY_COMPOSE_DIR:-}" ]]; then
  echo "DEPLOY_COMPOSE_DIR is required" >&2
  exit 1
fi

COMPOSE_FILE="${DEPLOY_COMPOSE_FILE:-deploy/docker-compose.prod.yml}"
VALID_SERVICES=("backend" "web" "admin")
SERVICES=()
CONTAINERS=()
DEPLOY_RETRIES="${DEPLOY_RETRIES:-3}"
DEPLOY_RETRY_DELAY="${DEPLOY_RETRY_DELAY:-10}"

is_valid_service() {
  local candidate="$1"
  local service

  for service in "${VALID_SERVICES[@]}"; do
    if [[ "$service" == "$candidate" ]]; then
      return 0
    fi
  done

  return 1
}

for service in "$@"; do
  if ! is_valid_service "$service"; then
    echo "Unsupported service: $service" >&2
    exit 1
  fi

  SERVICES+=("$service")
  CONTAINERS+=("gikky-$service")
done

if printf '%s\n' "${SERVICES[@]}" | grep -qx "backend"; then
  SERVICES+=("t0-worker" "t0-foreign-worker" "foreign-backfill-worker")
  CONTAINERS+=("gikky-t0-worker" "gikky-t0-foreign-worker" "gikky-foreign-backfill-worker")
fi

cd "$DEPLOY_COMPOSE_DIR"

echo "[$(date -Iseconds)] Deploy start"
echo "Ref: ${DEPLOY_REF:-unknown}"
echo "SHA: $COMMIT_SHA"
echo "Services: ${SERVICES[*]}"

git config --global --add safe.directory "$DEPLOY_COMPOSE_DIR"
git fetch origin main
git reset --hard "$COMMIT_SHA"

deploy_with_retry() {
  local attempt=1

  while true; do
    docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true

    if docker compose --env-file .env -f "$COMPOSE_FILE" pull "${SERVICES[@]}" && \
      docker compose --env-file .env -f "$COMPOSE_FILE" up -d --no-deps "${SERVICES[@]}"; then
      return 0
    fi

    if [[ "$attempt" -ge "$DEPLOY_RETRIES" ]]; then
      echo "Deploy failed after ${DEPLOY_RETRIES} attempts" >&2
      return 1
    fi

    echo "Deploy attempt ${attempt}/${DEPLOY_RETRIES} failed. Retrying in ${DEPLOY_RETRY_DELAY}s..." >&2
    attempt=$((attempt + 1))
    sleep "$DEPLOY_RETRY_DELAY"
  done
}

deploy_with_retry
docker compose --env-file .env -f "$COMPOSE_FILE" ps "${SERVICES[@]}"
docker image prune -f || true

echo "[$(date -Iseconds)] Deploy complete"
