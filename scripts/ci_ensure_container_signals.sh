#!/usr/bin/env bash
# Verify that processes inside a restricted candidate container can signal each other
# (kill their own pid), which the supervisor relies on to stop an over-limit candidate.
# On Ubuntu runners the default AppArmor container profile can deny this (EPERM). If so,
# switch Podman's default AppArmor profile to unconfined for this job and re-check; fail
# with diagnostics if signalling still does not work. Run as root, after the image pull.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
image="$(PYTHONPATH="$root/src" "$root/.venv/bin/python" -c 'from codegen_eval.sandbox import IMAGE; print(IMAGE)')"

probe() {
  podman run --rm --pull=never --network=none --read-only --cap-drop=ALL \
    --security-opt=no-new-privileges --user=65534:65534 "$image" python -c '
import os, signal
signal.signal(signal.SIGUSR1, lambda *a: None)
os.kill(os.getpid(), signal.SIGUSR1)
print("signals ok")
' 2>&1
}

if out="$(probe)"; then
  echo "$out"
  echo "::notice title=Container signals::allowed under the default security profile"
  exit 0
fi
echo "$out"
denied="$(dmesg 2>/dev/null | grep -i 'apparmor="DENIED"' | grep -i signal | tail -3 || true)"
echo "::warning title=Container signals denied::${out//$'\n'/ | } ${denied//$'\n'/ | }"

if ! command -v aa-status >/dev/null && [ ! -d /sys/kernel/security/apparmor ]; then
  echo "AppArmor is not active, so it is not the cause; not changing the profile" >&2
  exit 1
fi
mkdir -p /etc/containers/containers.conf.d
printf '[containers]\napparmor_profile = "unconfined"\n' > /etc/containers/containers.conf.d/50-ci-apparmor.conf
if out="$(probe)"; then
  echo "$out"
  echo "::notice title=Container signals::allowed only with AppArmor unconfined (runner-only difference, see docs/threat_model.md)"
  exit 0
fi
echo "$out" >&2
echo "::error title=Container signals still denied::${out//$'\n'/ | }"
exit 1
