#!/usr/bin/env bash
set -euo pipefail

# Runs only against a uniquely named, disposable Compose project. Docker Desktop
# or Docker Engine must be running. Set KEEP_SMOKE_STACK=1 to retain artifacts.
repository_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repository_root"
smoke_suffix=$(date -u +%Y%m%d%H%M%S)-$$
export SMOKE_PROJECT_NAME="ahinarena-smoke-$smoke_suffix"
export SMOKE_VOLUME_NAME="ahinarena-smoke-postgres-$smoke_suffix"
export INGRESS_NETWORK="ahinarena-smoke-ingress-$smoke_suffix"
smoke_dir=$(mktemp -d)
environment_file="$smoke_dir/production.env"
bot_dir="$smoke_dir/bots"
bot_sandbox_dir="$smoke_dir/bot-sandbox"
compose=(docker compose --env-file "$environment_file" -f deploy/compose.production.yaml -f deploy/compose.smoke.yaml)

cleanup() {
  status=$?
  if [[ "${KEEP_SMOKE_STACK:-}" != "1" ]]; then
    "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
    docker network rm "$INGRESS_NETWORK" >/dev/null 2>&1 || true
    rm -rf "$smoke_dir"
  else
    printf 'Keeping smoke stack: project=%s env=%s\n' "$SMOKE_PROJECT_NAME" "$environment_file"
  fi
  exit "$status"
}
trap cleanup EXIT

if ! docker info >/dev/null 2>&1; then
  echo "Docker Engine/Desktop must be running." >&2
  exit 1
fi
if stat -c '%g' /var/run/docker.sock >/dev/null 2>&1; then
  docker_socket_gid=$(stat -c '%g' /var/run/docker.sock)
else
  docker_socket_gid=$(stat -f '%g' /var/run/docker.sock)
fi
mkdir -p "$bot_dir" "$bot_sandbox_dir"
docker network create "$INGRESS_NETWORK" >/dev/null

cat >"$environment_file" <<EOF
API_IMAGE=ahinarena-api:smoke
WORKER_IMAGE=ahinarena-worker:smoke
BOT_SANDBOX_IMAGE=ahinarena-bot-runner:smoke
POSTGRES_DB=ahin_arena
POSTGRES_USER=ahin_arena
POSTGRES_PASSWORD=smoke-only-password
DATABASE_URL=postgresql+psycopg://ahin_arena:smoke-only-password@postgres:5432/ahin_arena
CORS_ALLOWED_ORIGINS=https://smoke.invalid
FRONTEND_URL=https://smoke.invalid
RESEND_API_KEY=smoke-only-resend-key-123456
EMAIL_FROM=smoke@invalid.test
DOCKER_SOCKET_GID=$docker_socket_gid
BOT_SANDBOX_HOST_DIR=$bot_sandbox_dir
INGRESS_NETWORK=$INGRESS_NETWORK
WORKER_POLL_INTERVAL_SECONDS=1
EOF

docker build -t ahinarena-api:smoke -f docker/api.Dockerfile .
docker build -t ahinarena-worker:smoke -f docker/worker.Dockerfile .
docker build -t ahinarena-bot-runner:smoke -f docker/bot_runner/Dockerfile .
docker run --rm -i --platform linux/amd64 -v "$bot_dir:/output" alpine:3.20 sh -c \
  'apk add --no-cache build-base >/dev/null && cc -O2 -static -s -DBOARD_SIZE=3 -x c - -o /output/one && cp /output/one /output/two' \
  < players/builtin_player.c

"${compose[@]}" up -d --wait postgres
"${compose[@]}" up --no-deps --abort-on-container-exit --exit-code-from migrate migrate
"${compose[@]}" up -d --no-deps --wait api worker

client=(docker run --rm -i --network "$INGRESS_NETWORK" -v "$bot_dir:/bots:ro" python:3.12-slim python -)
smoke_email="a-smoke-$smoke_suffix@invalid.test"
# Usernames are capped at 20 characters; time plus PID remains unique per run.
smoke_username="smoke$(date -u +%H%M%S)$$"
"${client[@]}" < scripts/smoke_production_client.py --base-url http://api:8000 --email "$smoke_email" --username "$smoke_username" --password 'SmokePass123!' --register-only
verification_token=$("${compose[@]}" exec -T postgres psql -U ahin_arena -d ahin_arena -Atc "SELECT token FROM auth_tokens WHERE purpose = 'email_verification' ORDER BY id DESC LIMIT 1")
test -n "$verification_token"
"${client[@]}" < scripts/smoke_production_client.py --base-url http://api:8000 --email "$smoke_email" --username "$smoke_username" --password 'SmokePass123!' --already-registered --verification-token "$verification_token" --bot-dir /bots

"${compose[@]}" restart api worker
"${compose[@]}" up -d --wait api worker
"${client[@]}" < scripts/smoke_production_client.py --base-url http://api:8000 --email ignored@invalid.test --username ignored --password ignored --check-only
persisted_matches=$("${compose[@]}" exec -T postgres psql -U ahin_arena -d ahin_arena -Atc 'SELECT count(*) FROM matches')
test "$persisted_matches" -ge 1
printf 'Production-style smoke test passed: project=%s persisted_matches=%s\n' "$SMOKE_PROJECT_NAME" "$persisted_matches"
