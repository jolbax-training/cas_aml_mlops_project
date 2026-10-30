#!/usr/bin/env bash
# Local MLflow tracking service in Podman: pinned image, durable host storage, localhost only.
#
#   scripts/mlflow_service.sh start|stop|restart|status|logs|down
#
# `stop` keeps the container; `down` removes it. Neither touches the data directory, which
# holds the SQLite backend store and the artifact store. Overrides (all optional):
#   MLFLOW_PORT            host port on 127.0.0.1                    (default 5000)
#   MLFLOW_DATA_DIR        host directory for durable data           (default ./mlflow_data)
#   MLFLOW_CONTAINER_NAME  container name                            (default codegen-eval-mlflow)
#   MLFLOW_IMAGE           image reference; keep it pinned by digest
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# MLflow 3.17.2, matching the client version locked in uv.lock (index digest, pulled 2026-10-30).
IMAGE="${MLFLOW_IMAGE:-ghcr.io/mlflow/mlflow@sha256:1a8e9dba1e19431f175f6d28aac94b0d5790e0c9a9d05d1205c6054bbd3085ac}"
PORT="${MLFLOW_PORT:-5000}"
DATA_DIR="${MLFLOW_DATA_DIR:-$ROOT/mlflow_data}"
NAME="${MLFLOW_CONTAINER_NAME:-codegen-eval-mlflow}"
URL="http://127.0.0.1:${PORT}"

exists() { podman container exists "$NAME"; }
running() { [ "$(podman inspect --format '{{.State.Running}}' "$NAME" 2>/dev/null || true)" = "true" ]; }

wait_healthy() {
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 "$URL/health" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  echo "MLflow did not become healthy at $URL; see: $0 logs" >&2
  return 1
}

# An existing container keeps the port, image, and data directory it was created with, so
# refuse to reuse it when the current settings differ (the URL printed would be wrong).
check_matches() {
  local image port mount
  image="$(podman inspect --format '{{.ImageName}}' "$NAME")"
  port="$(podman inspect --format '{{json .HostConfig.PortBindings}}' "$NAME")"
  mount="$(podman inspect --format '{{range .Mounts}}{{.Source}} {{end}}' "$NAME")"
  if [ "$image" != "$IMAGE" ] || [[ "$port" != *'"HostIp":"127.0.0.1","HostPort":"'"${PORT}"'"'* ]] \
      || [[ " $mount " != *" ${DATA_DIR} "* ]]; then
    echo "container $NAME exists with different settings (image: $image, port: $port, data: $mount)." >&2
    echo "Run '$0 down' first (data is kept), then start again." >&2
    exit 1
  fi
}

start() {
  mkdir -p "$DATA_DIR"
  if exists; then check_matches; fi
  if running; then
    echo "already running at $URL"
  elif exists; then
    podman start "$NAME" >/dev/null
  else
    # The server alone sees the data directory. The artifact store is proxied by the server,
    # so clients upload over HTTP and need no filesystem or storage credentials.
    podman run -d --name "$NAME" --pull=never \
      --publish "127.0.0.1:${PORT}:5000" \
      --volume "${DATA_DIR}:/mlflow" \
      "$IMAGE" mlflow server --host 0.0.0.0 --port 5000 \
      --backend-store-uri sqlite:////mlflow/mlflow.db \
      --artifacts-destination /mlflow/artifacts --serve-artifacts >/dev/null
  fi
  wait_healthy
  echo "MLflow running at $URL (data: $DATA_DIR)"
}

stop() { if exists; then podman stop -t 20 "$NAME" >/dev/null; fi; echo "stopped (data kept in $DATA_DIR)"; }

status() {
  if running; then
    if curl -fsS --max-time 2 "$URL/health" >/dev/null 2>&1; then echo "running and healthy at $URL"; else echo "running but not healthy at $URL"; exit 1; fi
  elif exists; then echo "stopped (container exists)"; exit 1
  else echo "not created"; exit 1; fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) podman logs --tail 100 "$NAME" ;;
  down) if exists; then podman rm -f -t 20 "$NAME" >/dev/null; fi; echo "container removed (data kept in $DATA_DIR)" ;;
  *) echo "usage: $0 start|stop|restart|status|logs|down" >&2; exit 2 ;;
esac
