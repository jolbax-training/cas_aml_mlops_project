#!/bin/sh
# Repeat wait.sh until an actionable message (worker_done, question, escalation) arrives.
# Batches without one (heartbeats) are acked automatically; the actionable delivery is printed and NOT acked:
# ack it yourself with `wait.sh --ack <id>` (or `orca orchestration check --ack <id>`) after processing it.
# Usage: waitloop.sh [--rounds <n>] [--ack <delivery_id>] [--terminal <handle>] [--types <a,b>] [--timeout-ms <n>] [--dry-run] [--help]
# Exit: 0 actionable message printed, 1 no actionable message in <n> rounds (default 8), 2 wait.sh failed.
DIR=$(dirname "$0"); ROUNDS=8; ACK=""; PASS=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; exit 0 ;;
    --dry-run) DRY=1; PASS="$PASS --dry-run" ;;
    --rounds) ROUNDS="$2"; shift ;;
    --ack) ACK="$2"; shift ;;
    --terminal|--types|--timeout-ms) PASS="$PASS $1 $2"; shift ;;
    -*) echo "waitloop.sh: unknown option $1" >&2; exit 2 ;;
    *) ACK="$1" ;;
  esac
  shift
done

i=0
while [ "$i" -lt "$ROUNDS" ]; do
  i=$((i + 1))
  # shellcheck disable=SC2086
  if [ -n "$ACK" ]; then out=$("$DIR/wait.sh" $PASS --ack "$ACK"); else out=$("$DIR/wait.sh" $PASS); fi
  rc=$?
  if [ "$rc" -ne 0 ]; then echo "$out"; [ -n "$ACK" ] && echo "last delivery $ACK still unacked"; exit 2; fi
  if [ "$DRY" = 1 ]; then echo "$out"; exit 0; fi
  if echo "$out" | grep -qE '^--- (worker_done|question|escalation) '; then
    echo "$out"
    exit 0
  fi
  ACK=$(echo "$out" | awk '/^delivery /{ if ($2 != "None" && $2 != "") print $2 }')
done
echo "no actionable message after $ROUNDS rounds${ACK:+; last delivery $ACK still unacked}"
exit 1
