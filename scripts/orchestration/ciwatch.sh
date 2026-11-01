#!/bin/sh
# Wait for a GitHub Actions run to finish, then print its result, jobs, failing steps, and check-run annotations.
# Annotations are read instead of logs because raw logs need authentication; the unauthenticated API allows 60 requests/hour.
# Usage: ciwatch.sh [--repo <owner/repo>] [--interval <seconds>] [--max-polls <n>] [--dry-run] [--help] <run_id>
# Repository: --repo, else $CIWATCH_REPO, else parsed from the `origin` remote. API base: $CIWATCH_API (default https://api.github.com).
# Exit: 0 run succeeded, 1 run finished without success, 2 API error or rate limit, 3 still running after --max-polls (default 200).
REPO="${CIWATCH_REPO:-}"; INTERVAL=150; MAXPOLLS=200; DRY=0; RUN=""
API="${CIWATCH_API:-https://api.github.com}"
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; exit 0 ;;
    --dry-run) DRY=1 ;;
    --repo) REPO="$2"; shift ;;
    --interval) INTERVAL="$2"; shift ;;
    --max-polls) MAXPOLLS="$2"; shift ;;
    -*) echo "ciwatch.sh: unknown option $1" >&2; exit 2 ;;
    *) RUN="$1" ;;
  esac
  shift
done
[ -n "$RUN" ] || { echo "ciwatch.sh: run id required (see --help)" >&2; exit 2; }
if [ -z "$REPO" ]; then
  url=$(git remote get-url origin 2>/dev/null)
  REPO=$(printf '%s' "$url" | sed -E 's#^(git@[^:]+:|https?://[^/]+/|ssh://[^/]+/)##; s#\.git$##')
fi
case "$REPO" in */*) ;; *) echo "ciwatch.sh: cannot determine repository; pass --repo <owner/repo>" >&2; exit 2 ;; esac
A="$API/repos/$REPO"
if [ "$DRY" = 1 ]; then echo "curl -s --max-time 30 $A/actions/runs/$RUN (every ${INTERVAL}s, up to $MAXPOLLS polls)"; exit 0; fi

# prints "<status>|<conclusion>" for a run body, or "error|<message>" when the body is an API error
field() { python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    print("error|response is not JSON"); sys.exit()
if "status" in d: print("%s|%s" % (d.get("status"), d.get("conclusion")))
else: print("error|%s" % str(d.get("message", d))[:300])'; }

n=0; blips=0
while :; do
  body=$(curl -s --max-time 30 "$A/actions/runs/$RUN")
  st=$(printf '%s' "$body" | field)
  case "$st" in
    error\|response\ is\ not\ JSON)
      # a dropped connection gives an empty body: tolerate three in a row before giving up
      blips=$((blips + 1))
      [ "$blips" -ge 3 ] && { echo "ciwatch.sh: no usable response from $A/actions/runs/$RUN ($blips tries in a row)"; exit 2; } ;;
    error\|*) echo "ciwatch.sh: GitHub API error for $A/actions/runs/$RUN: ${st#error|}"; exit 2 ;;
    completed\|*) break ;;
    *) blips=0 ;;
  esac
  n=$((n + 1))
  [ "$n" -ge "$MAXPOLLS" ] && { echo "ciwatch.sh: run $RUN still ${st%%|*} after $n polls"; exit 3; }
  sleep "$INTERVAL"
done

printf '%s' "$body" | python3 -c '
import json, sys
r = json.load(sys.stdin)
print("run", r["id"], r["head_sha"][:7], r["conclusion"], r["html_url"])'
jobs=$(curl -s --max-time 30 "$A/actions/runs/$RUN/jobs")
ids=$(printf '%s' "$jobs" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(*[j["id"] for j in d["jobs"]], sep="\n")
except (ValueError, KeyError, TypeError):
    print("jobs unavailable (empty, rate-limited, or unexpected response)", file=sys.stderr)')
for J in $ids; do
  curl -s --max-time 30 "$A/actions/jobs/$J" | python3 -c '
import json, sys
try:
    j = json.load(sys.stdin)
    print("job", j["name"], j["conclusion"], [s["name"] for s in j["steps"] if s["conclusion"] not in ("success", "skipped")])
except (ValueError, KeyError, TypeError):
    print("job", sys.argv[1], "unavailable (empty, rate-limited, or unexpected response)")' "$J"
  curl -s --max-time 30 "$A/check-runs/$J/annotations" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    d = {"message": "response is not JSON"}
if isinstance(d, dict):
    print("  annotations unavailable:", d.get("message", d)); sys.exit()
for a in d:
    if "Node.js 20" not in a["message"]:
        print("  ", a["annotation_level"], a.get("title") or "", a["message"][:500].replace("\n", " | "))'
done
case "$st" in completed\|success) exit 0 ;; *) exit 1 ;; esac
