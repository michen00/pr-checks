#!/bin/sh
# Validate a release version and print it as vMAJOR.MINOR.PATCH.
#
# Usage: parse-version.sh <version> [--require-v]
#
# With --require-v the leading v is mandatory. Exits 1 on an invalid version and 2
# on bad arguments. Callers pass workflow inputs, commit subjects and run names, so
# anything but three dot-separated runs of digits is refused.

set -eu

usage() {
  echo "Usage: $0 <version> [--require-v]" >&2
  exit 2
}

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  usage
fi

version="$1"
require_v=0

if [ "$#" -eq 2 ]; then
  case "$2" in
    --require-v) require_v=1 ;;
    *) usage ;;
  esac
fi

if [ "$require_v" -eq 1 ]; then
  expected='vX.Y.Z'
else
  expected='X.Y.Z or vX.Y.Z'
fi

invalid() {
  echo "Error: invalid version '$version'. Expected $expected." >&2
  exit 1
}

rest="${version#v}"

if [ "$require_v" -eq 1 ] && [ "$rest" = "$version" ]; then
  invalid
fi

# "${x#*.}" leaves x unchanged when it has no dot, so each separator is checked.
major="${rest%%.*}"
after_major="${rest#*.}"
[ "$after_major" != "$rest" ] || invalid

minor="${after_major%%.*}"
patch="${after_major#*.}"
[ "$patch" != "$after_major" ] || invalid

# Component by component, because a glob such as v[0-9]*.[0-9]*.[0-9]* also
# matches "v1.0.0; rm -rf /".
for part in "$major" "$minor" "$patch"; do
  case "$part" in
    '' | *[!0-9]*) invalid ;;
  esac
done

echo "v$major.$minor.$patch"
