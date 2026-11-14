#!/usr/bin/env bash
# Tests for scripts/release/approve.sh, against a stub `gh` on PATH.
#
# The stub is driven by GH_STUB_* variables and logs every POST body with the
# endpoint it went to, which tells "would have approved" from "approved nothing".
# Setup fails fast and ends by asserting the stub is what `gh` resolves to:
# otherwise a `--yes` case would reach the caller's authenticated gh and approve a
# real release.

set -uo pipefail
TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPROVE="$TEST_SCRIPT_DIR/../../scripts/release/approve.sh"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

PASSED=0
FAILED=0

pass() {
  echo -e "${GREEN}✓${NC} $1"
  ((PASSED++))
}

fail() {
  echo -e "${RED}✗${NC} $1"
  shift
  for msg in "$@"; do
    echo -e "  ${YELLOW}$msg${NC}"
  done
  ((FAILED++))
}

setup_failed() {
  echo -e "${RED}✗${NC} test setup failed: $1" >&2
  exit 1
}

STUB_DIR="$(mktemp -d)" || setup_failed "mktemp -d"
trap 'rm -rf "$STUB_DIR"' EXIT

cat > "$STUB_DIR/gh" << 'STUB' || setup_failed "writing the gh stub"
#!/usr/bin/env bash
case "$1" in
run) printf '%s\n' "${GH_STUB_WAITING:-[]}" ;;
repo) printf '%s\n' "${GH_STUB_REPO:-michen00/pr-checks}" ;;
release)
	[ -n "${GH_STUB_RELEASE_FAIL:-}" ] && exit 1
	printf '%s\n' "${GH_STUB_RELEASES:-[]}"
	;;
pr) printf '%s\n' "${GH_STUB_OPENPR:-}" ;;
api)
	endpoint=""
	for arg in "$@"; do
		case "$arg" in repos/*) endpoint="$arg" ;; esac
	done
	for arg in "$@"; do
		if [ "$arg" = "POST" ]; then
			jq -c --arg endpoint "$endpoint" '. + {endpoint: $endpoint}' \
				>>"${GH_STUB_POST_LOG:-/dev/null}"
			echo '{}'
			exit 0
		fi
	done
	printf '%s\n' "${GH_STUB_PENDING:-[]}"
	;;
esac
exit 0
STUB

[ -s "$STUB_DIR/gh" ] || setup_failed "gh stub is empty"
chmod +x "$STUB_DIR/gh" || setup_failed "chmod +x on the gh stub"

resolved="$(PATH="$STUB_DIR:$PATH" command -v gh)"
[ "$resolved" = "$STUB_DIR/gh" ] ||
  setup_failed "gh resolves to '$resolved', not the stub"

COMMIT="cccccccccccccccccccccccccccccccccccccccc"

# waiting_run <event> <branch> <title> [sha] -- one waiting Release Tag run, id 42.
waiting_run() {
  jq -nc --arg event "$1" --arg branch "$2" --arg title "$3" --arg sha "${4-$COMMIT}" \
    '[{databaseId: 42, displayTitle: $title, event: $event, headBranch: $branch,
       headSha: $sha, url: "https://example.invalid/run/42"}]'
}

WAITING_RUN="$(waiting_run push main 'chore(release): prepare v9.9.9 (#83)')"
PENDING_OK='[{"environment":{"id":7,"name":"release"},"current_user_can_approve":true}]'
PENDING_DENIED='[{"environment":{"id":7,"name":"release"},"current_user_can_approve":false}]'
PENDING_EXTRA='[{"environment":{"id":7,"name":"release"},"current_user_can_approve":true},{"environment":{"id":8,"name":"other"},"current_user_can_approve":true}]'

# run_approve <post_log> [args...] -- runs approve.sh with the stub on PATH. Stdin is
# /dev/null, so the prompt's terminal check is deterministic.
run_approve() {
  local log="$1"
  shift
  GH_STUB_POST_LOG="$log" PATH="$STUB_DIR:$PATH" sh "$APPROVE" "$@" < /dev/null 2>&1
}

# refused <description> <waiting-json> [pending-json] -- asserts approve.sh --yes
# exits 1 and approves nothing.
refused() {
  : > "$log"
  out="$(GH_STUB_WAITING="$2" GH_STUB_PENDING="${3:-$PENDING_OK}" \
    run_approve "$log" --yes)"
  status=$?
  if [ "$status" -eq 1 ] && [ ! -s "$log" ]; then
    pass "$1"
  else
    fail "$1" "Exited $status. Got: $out"
  fi
}

log="$STUB_DIR/post.log"

# --- arguments and an idle repository ----------------------------------------

PATH="$STUB_DIR:$PATH" sh "$APPROVE" --bogus > /dev/null 2>&1
if [ "$?" -eq 2 ]; then
  pass "unknown flag exits 2"
else
  fail "unknown flag" "Expected exit 2"
fi

: > "$log"
out="$(GH_STUB_WAITING='[]' run_approve "$log")"
status=$?
if [ "$status" -eq 1 ] && [[ $out == *"Nothing to release"* ]] && [ ! -s "$log" ]; then
  pass "no waiting run exits 1, says so, and approves nothing"
else
  fail "no waiting run" "Exited $status. Got: $out"
fi

# --- status ------------------------------------------------------------------

out="$(GH_STUB_RELEASES='[{"tagName":"v0.1.2"}]' run_approve "$log" --status)"
status=$?
if [ "$status" -eq 0 ] && [[ $out == *"Awaiting approval: none"* && $out == *"v0.1.2"* ]]; then
  pass "--status reports the latest release and nothing awaiting approval"
else
  fail "--status on an idle repository" "Exited $status. Got: $out"
fi

out="$(GH_STUB_RELEASES='[]' run_approve "$log" --status)"
status=$?
if [ "$status" -eq 0 ] && [[ $out == *"Latest release:    none"* ]]; then
  pass "--status reports 'none' for a repository with no releases"
else
  fail "--status with no releases" "Exited $status. Got: $out"
fi

# A failed lookup must not read as a repository with no releases.
out="$(GH_STUB_RELEASE_FAIL=1 run_approve "$log" --status)"
status=$?
if [ "$status" -eq 1 ] && [[ $out != *"Latest release:    none"* ]]; then
  pass "--status fails when the release lookup errors"
else
  fail "--status on a failed lookup" "Exited $status. Got: $out"
fi

: > "$log"
out="$(GH_STUB_WAITING="$WAITING_RUN" GH_STUB_OPENPR='#83 chore(release): prepare v9.9.9' \
  run_approve "$log" --status)"
status=$?
if [ "$status" -eq 0 ] && [[ $out == *"v9.9.9 tag"* && $out == *"https://example.invalid/run/42"* ]]; then
  pass "--status names the pending tag and links the run"
else
  fail "--status with a run in flight" "Exited $status. Got: $out"
fi
if [ -s "$log" ]; then
  fail "--status is read-only" "A POST was sent"
else
  pass "--status approves nothing"
fi

# --- refusing to approve -----------------------------------------------------

: > "$log"
out="$(GH_STUB_WAITING="$WAITING_RUN" GH_STUB_PENDING="$PENDING_OK" run_approve "$log")"
status=$?
if [ "$status" -eq 1 ] && [[ $out == *"not a terminal"* ]] && [ ! -s "$log" ]; then
  pass "refuses to approve unprompted without --yes"
else
  fail "non-tty without --yes" "Exited $status. Got: $out"
fi

refused "a non-approver is rejected" "$WAITING_RUN" "$PENDING_DENIED"
refused "a waiting run with no pending deployment is rejected" "$WAITING_RUN" '[]'
refused "a run waiting on more than the release environment is rejected" \
  "$WAITING_RUN" "$PENDING_EXTRA"

# A run's workflow file comes from the ref it started on, so only a push to main
# runs main's.
refused "a run started by a push to another branch is rejected" \
  "$(waiting_run push feature 'chore(release): prepare v9.9.9 (#83)')"
refused "a run started by a dispatch is rejected" \
  "$(waiting_run workflow_dispatch main 'chore(release): prepare v9.9.9 (#83)')"
refused "a run started by a pull request is rejected" \
  "$(waiting_run pull_request release/v9.9.9 'chore(release): prepare v9.9.9 (#83)')"

# The subject is written by whoever merged, so it is parsed as strictly as the
# workflow parses it.
refused "a run for a commit that is not a release is rejected" \
  "$(waiting_run push main 'fix: a bug (#84)')"
refused "a subject that is not a clean vX.Y.Z is rejected" \
  "$(waiting_run push main 'chore(release): prepare v1.0.0; rm -rf / (#85)')"
refused "a run that names no commit is rejected" \
  "$(waiting_run push main 'chore(release): prepare v9.9.9 (#83)' '')"

# --- the approving path ------------------------------------------------------

: > "$log"
out="$(GH_STUB_WAITING="$WAITING_RUN" GH_STUB_PENDING="$PENDING_OK" \
  run_approve "$log" --yes)"
status=$?
if [ "$status" -ne 0 ] || [ ! -s "$log" ]; then
  fail "--yes approves" "Exited $status. Output: $out"
elif [ "$(jq -cs 'map({state, environment_ids, endpoint})' "$log")" = \
  '[{"state":"approved","environment_ids":[7],"endpoint":"repos/michen00/pr-checks/actions/runs/42/pending_deployments"}]' ]; then
  pass "--yes POSTs one approval of the release environment for the run"
else
  fail "--yes POSTs the right body" "Got: $(cat "$log")"
fi

if [[ $out == *"v9.9.9"* && $out == *"Major tag:      v9"* && $out == *"$COMMIT"* ]]; then
  pass "the summary names the tag, its major tag and the commit"
else
  fail "the summary names what will be tagged" "Got: $out"
fi

rebased="$(waiting_run push main 'chore(release): prepare v0.3.1')"
out="$(GH_STUB_WAITING="$rebased" GH_STUB_PENDING="$PENDING_OK" run_approve "$log" --yes)"
status=$?
if [ "$status" -eq 0 ] && [[ $out == *"Major tag:      v0"* ]]; then
  pass "a rebase-merged release commit, with no PR number, is approved too"
else
  fail "a subject without a PR number" "Exited $status. Got: $out"
fi

printf "\nResults: ${GREEN}%d passed${NC}, ${RED}%d failed${NC}\n" "$PASSED" "$FAILED"

[ "$FAILED" -eq 0 ]
