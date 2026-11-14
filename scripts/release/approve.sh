#!/bin/sh
# Approve the Release Tag run waiting on the protected `release` environment.
#
# Usage: approve.sh [--status] [--yes]
#
# Merging a release PR tags nothing by itself: Release Tag waits on the `release`
# environment, with no timeout and no reminder. --status reports where a release
# stands and changes nothing. A bare run prints the tag the run would create and the
# commit it would point at, then asks; --yes skips the question and is required when
# stdin is not a terminal. Requires an authenticated `gh` and `jq`. Exits 1 when
# nothing is waiting.

set -eu

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
TAG_WORKFLOW="release-tag.yml"
RELEASE_BRANCH="main"

usage() {
  echo "Usage: $0 [--status] [--yes]" >&2
  exit 2
}

die() {
  echo "Error: $1" >&2
  exit 1
}

mode="approve"
assume_yes=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --status) mode="status" ;;
    --yes | -y) assume_yes=1 ;;
    *) usage ;;
  esac
  shift
done

for tool in gh jq; do
  command -v "$tool" > /dev/null 2>&1 ||
    die "$tool is required but not installed."
done

repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)" ||
  die "Could not resolve the repository. Is gh authenticated?"

# The newest waiting run, as a JSON array of at most one. Release Tag's job holds a
# concurrency group, so no more than one run of main's workflow file waits at once.
waiting="$(gh run list --workflow="$TAG_WORKFLOW" --status waiting --limit 1 \
  --json databaseId,displayTitle,event,headBranch,headSha,url)" ||
  die "Could not list $TAG_WORKFLOW runs."

field() {
  printf '%s' "$waiting" | jq -r ".[0].$1 // empty"
}

run_id="$(field databaseId)"
run_url="$(field url)"
title="$(field displayTitle)"

if [ "$mode" = "status" ]; then
  # `list` returns [] for a repository with no release and fails on an error, which
  # `gh release view` reports alike.
  releases="$(gh release list --limit 1 --json tagName)" ||
    die "Could not read releases."
  latest="$(printf '%s' "$releases" | jq -r '.[0].tagName // "none"')"
  echo "Latest release:    $latest"

  open_pr="$(gh pr list --state open --limit 100 \
    --json number,title,headRefName \
    --jq '[.[] | select(.headRefName | startswith("release/"))]
      | map("#\(.number) \(.title)") | join(", ") // empty')" ||
    die "Could not list open pull requests."
  echo "Open release PR:   ${open_pr:-none}"

  if [ -n "$run_id" ]; then
    tag="$("$SCRIPT_DIR/subject-tag.sh" "$title" 2> /dev/null)" || tag="(unnamed)"
    echo "Awaiting approval: $tag tag — $run_url"
    echo
    echo "Run 'make release-approve' to approve."
  else
    echo "Awaiting approval: none"
  fi
  exit 0
fi

[ -n "$run_id" ] ||
  die "No Release Tag run is awaiting approval. Nothing to release."

# A run's workflow file is read from the ref the run started on, and the release
# key may only be handed to main's.
origin="$(printf '%s' "$waiting" | jq -r '.[0] | "\(.event) \(.headBranch)"')"
[ "$origin" = "push $RELEASE_BRANCH" ] ||
  die "Release Tag run $run_id started from '$origin', not a push to $RELEASE_BRANCH: $run_url. Reject it on GitHub."

tag="$("$SCRIPT_DIR/subject-tag.sh" "$title" 2> /dev/null)" ||
  die "Release Tag run $run_id is for '$title', which names no vX.Y.Z release: $run_url. Reject it on GitHub."
major="${tag%%.*}"

# The run checks out the commit it started on, so that is the commit tagged.
commit="$(field headSha)"
printf '%s' "$commit" | grep -Eq '^[0-9a-f]{40}$' ||
  die "Release Tag run $run_id names no commit: $run_url."

pending="$(gh api "repos/$repo/actions/runs/$run_id/pending_deployments")" ||
  die "Could not read pending deployments for run $run_id."

[ "$(printf '%s' "$pending" | jq 'length')" -gt 0 ] ||
  die "Run $run_id is waiting, but no deployment is pending your approval."

[ "$(printf '%s' "$pending" | jq -r 'all(.current_user_can_approve)')" = "true" ] ||
  die "You are not an approver for the environment gating run $run_id."

env_ids="$(printf '%s' "$pending" | jq -c '[.[].environment.id]')"
env_names="$(printf '%s' "$pending" | jq -r '[.[].environment.name] | join(", ")')"
[ "$env_names" = "release" ] ||
  die "Run $run_id waits on '$env_names', not on the release environment alone."

cat << SUMMARY
Release awaiting approval
  Tag to create:  $tag
  Major tag:      $major
  Commit:         $commit
  Environment:    $env_names
  Run:            $run_url

Approving creates and pushes the GPG-signed tag $tag, moves $major to the same
commit, and publishes the GitHub release.
SUMMARY

if [ "$assume_yes" -eq 0 ]; then
  [ -t 0 ] ||
    die "stdin is not a terminal; pass --yes to approve without a prompt."
  printf 'Approve %s? [y/N] ' "$tag"
  read -r reply
  case "$reply" in
    [yY] | [yY][eE][sS]) ;;
    *)
      echo "Aborted. Nothing was approved." >&2
      exit 0
      ;;
  esac
fi

jq -nc --argjson ids "$env_ids" \
  '{environment_ids: $ids, state: "approved",
    comment: "Approved via scripts/release/approve.sh"}' |
  gh api "repos/$repo/actions/runs/$run_id/pending_deployments" \
    --method POST --input - > /dev/null ||
  die "Approval failed for run $run_id."

echo "Approved. $tag will be tagged and released."
echo "Watch it: gh run watch $run_id"
