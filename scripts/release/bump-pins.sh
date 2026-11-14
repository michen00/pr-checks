#!/bin/sh
# Point this repository's own `uses:` pins at a release.
#
# Usage: bump-pins.sh <vX.Y.Z> [file...]
#
# Defaults to README.md. A pin of the check action to a full version,
# `michen00/pr-checks@vX.Y.Z`, moves to the release, and a pin to a major tag,
# `michen00/pr-checks@vN`, to the release's major tag. A pin to a branch or a
# commit is left alone, and so is every pin of the comment action, which callers
# pin by commit. Exits 2 on bad arguments and 3 when a file holds no version pin,
# so Release PR fails rather than ship a snippet that names no release.

set -eu

REPO_SLUG='michen00/pr-checks'

usage() {
  echo "Usage: $0 <vX.Y.Z> [file...]" >&2
  exit 2
}

if [ "$#" -lt 1 ]; then
  usage
fi

parse_version="$(dirname "$0")/parse-version.sh"
if ! tag="$("$parse_version" "$1" --require-v)"; then
  usage
fi
shift
major="${tag%%.*}"

if [ "$#" -eq 0 ]; then
  set -- README.md
fi

slug_pattern="$(printf '%s' "$REPO_SLUG" | sed 's/[./]/\\&/g')"
pin_pattern="${slug_pattern}@v[0-9]+"
full_pattern="${pin_pattern}\.[0-9]+\.[0-9]+"

status=0

for file in "$@"; do
  if [ ! -f "$file" ]; then
    echo "Error: file not found: $file" >&2
    exit 2
  fi

  if ! grep -Eq "${pin_pattern}" "$file"; then
    echo "Error: no $REPO_SLUG@v pin found in $file" >&2
    status=3
    continue
  fi

  # A pin ends at anything but a digit, or at a dot that ends a sentence, so a
  # match cannot stop inside a longer version.
  tmp="$(mktemp)"
  sed -E \
    -e "s/${full_pattern}([^0-9]|\$)/${slug_pattern}@${tag}\1/g" \
    -e "s/${pin_pattern}([^0-9.]|\.[^0-9]|\.?\$)/${slug_pattern}@${major}\1/g" \
    "$file" > "$tmp"

  if cmp -s "$tmp" "$file"; then
    echo "Already at $tag: $file"
  else
    cat "$tmp" > "$file"
    echo "Bumped to $tag: $file"
  fi
  rm -f "$tmp"
done

exit "$status"
