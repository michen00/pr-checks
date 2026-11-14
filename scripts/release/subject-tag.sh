#!/bin/sh
# Print the tag a release commit's subject names, as vX.Y.Z.
#
# Usage: subject-tag.sh <subject>
#
# A release commit's subject is the release PR's title, `chore(release): prepare
# vX.Y.Z`, followed by ` (#N)` when the PR was squash-merged. Exits 1 on any other
# subject and 2 on bad arguments.

set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <subject>" >&2
  exit 2
fi

prefix='chore(release): prepare '
rest="${1#"$prefix"}"
if [ "$rest" = "$1" ]; then
  echo "Error: not a release commit's subject: $1" >&2
  exit 1
fi

exec "$(dirname "$0")/parse-version.sh" "${rest%% *}" --require-v
