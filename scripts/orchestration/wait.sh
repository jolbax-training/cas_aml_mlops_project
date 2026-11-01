#!/bin/sh
# Block until a worker_done, escalation, or question message reaches the coordinator, then print a summary.
# Usage: wait.sh [--ack <delivery_id>] [--terminal <handle>] [--types <a,b>] [--timeout-ms <n>] [--dry-run] [--help]
#        wait.sh <delivery_id>        (positional form of --ack)
# Output: a "delivery <id> timedOut <bool> count <n>" line, then one "--- <type> <id> <from> <subject>" block per message.
# Exit: 0 summary printed (also on timeout), 2 Orca failed or returned something that is not the expected JSON.
# An actionable delivery stays unacked until the caller passes its id back with --ack; unacked batches are replayed.
ACK=""; TERMINAL=""; TYPES="worker_done,escalation,question"; TIMEOUT=590000; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --dry-run) DRY=1 ;;
    --ack) ACK="$2"; shift ;;
    --terminal) TERMINAL="$2"; shift ;;
    --types) TYPES="$2"; shift ;;
    --timeout-ms) TIMEOUT="$2"; shift ;;
    -*) echo "wait.sh: unknown option $1" >&2; exit 2 ;;
    *) ACK="$1" ;;
  esac
  shift
done

set -- orca orchestration check
[ -n "$TERMINAL" ] && set -- "$@" --terminal "$TERMINAL"
[ -n "$ACK" ] && set -- "$@" --ack "$ACK"
set -- "$@" --wait --types "$TYPES" --timeout-ms "$TIMEOUT" --json

if [ "$DRY" = 1 ]; then echo "$*"; exit 0; fi

ERR=$(mktemp); OUT=$(mktemp); trap 'rm -f "$ERR" "$OUT"' EXIT
"$@" >"$OUT" 2>"$ERR"; RC=$?
# stderr carries JSON keepalive lines; anything else is a diagnostic worth showing
grep -v _keepalive "$ERR" >&2
python3 - "$RC" "$OUT" <<'PY'
import json, sys
rc, path = int(sys.argv[1]), sys.argv[2]
raw = open(path).read()
try:
    d = json.loads(raw)
    if not isinstance(d, dict) or rc != 0 or d.get("ok") is False:
        raise ValueError("orca failed or the response is not an object")
    d = d.get("result", d)
    if not isinstance(d, dict) or "count" not in d and "messages" not in d:
        raise ValueError("no delivery in response")
except ValueError:
    print("wait.sh: orca returned no usable delivery (exit %d):" % rc)
    print(raw.strip() or "(empty)")
    sys.exit(2)
print("delivery", d.get("deliveryId"), "timedOut", d.get("timedOut"), "count", d.get("count"))
for m in d.get("messages", []):
    print("---", m.get("type"), m.get("id"), m.get("from_handle"), m.get("subject"))
    print(m.get("body"))
    print(m.get("payload"))
PY
