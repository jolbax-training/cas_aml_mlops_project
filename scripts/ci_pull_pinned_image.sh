#!/usr/bin/env bash
# Pull the digest-pinned candidate image with retries and verify the digest.
# Usage: ci_pull_pinned_image.sh   (reads the image from codegen_eval.sandbox.IMAGE)
# With CI_IMAGE_MIRROR set (e.g. public.ecr.aws/docker/library) and root privileges, a
# registries.conf mirror is configured for docker.io/library first; the pull is still by
# the same digest, so the content is identical and a mirror miss falls back to Docker Hub.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
image="$(PYTHONPATH="$root/src" "$root/.venv/bin/python" -c 'from codegen_eval.sandbox import IMAGE; print(IMAGE)')"
digest="sha256:${image##*@sha256:}"
echo "image: $image"

if [ -n "${CI_IMAGE_MIRROR:-}" ]; then
  sudo mkdir -p /etc/containers/registries.conf.d
  sudo tee /etc/containers/registries.conf.d/50-ci-mirror.conf >/dev/null <<CONF
[[registry]]
prefix = "docker.io/library"
location = "docker.io/library"

[[registry.mirror]]
location = "${CI_IMAGE_MIRROR}"
CONF
fi

attempts=4
for attempt in $(seq 1 "$attempts"); do
  if podman pull "$image"; then
    break
  fi
  if [ "$attempt" -eq "$attempts" ]; then
    echo "could not pull $image after $attempts attempts" >&2
    exit 1
  fi
  delay=$((attempt * 20))
  echo "pull attempt $attempt failed; retrying in ${delay}s" >&2
  sleep "$delay"
done

actual="$(podman image inspect "$image" --format '{{.Digest}}')"
echo "digest=$actual"
if [ "$actual" != "$digest" ]; then
  echo "pulled digest $actual does not match pinned $digest" >&2
  exit 1
fi
