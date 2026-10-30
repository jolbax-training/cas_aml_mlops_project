#!/usr/bin/env bash
# Fail fast, with a diagnostic, unless Podman can enforce the memory, pids, and cpu limits
# the isolation probes assert. Run after the pinned image has been pulled.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
image="$(PYTHONPATH="$root/src" "$root/.venv/bin/python" -c 'from codegen_eval.sandbox import IMAGE; print(IMAGE)')"

podman --version
podman info --format 'rootless={{.Host.Security.Rootless}} cgroupsVersion={{.Host.CgroupsVersion}} manager={{.Host.CgroupManager}} runtime={{.Host.OCIRuntime.Name}} arch={{.Host.Arch}}'
controllers="$(podman info --format '{{.Host.CgroupControllers}}')"
echo "cgroup controllers: $controllers"
for needed in memory pids cpu; do
  case " ${controllers//[\[\]]/} " in
    *" $needed "*) ;;
    *) echo "cgroup controller '$needed' is not available to Podman; limits cannot be enforced" >&2; exit 1 ;;
  esac
done

# Start a container with limits like the sandbox's and read them back from its cgroup.
observed="$(podman run --rm --pull=never --network=none --pids-limit=32 --memory=128m \
  --memory-swap=128m --cpus=1 "$image" \
  python -c 'print(open("/sys/fs/cgroup/memory.max").read().strip(), open("/sys/fs/cgroup/pids.max").read().strip(), open("/sys/fs/cgroup/cpu.max").read().strip())')"
echo "observed memory.max pids.max cpu.max: $observed"
if [ "$observed" != "134217728 32 100000 100000" ]; then
  echo "container cgroup limits were not applied (expected '134217728 32 100000 100000')" >&2
  exit 1
fi
echo "limits enforced"
