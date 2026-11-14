#!/bin/sh
# Regenerate the changelog with the release under preparation as its own section.
#
# Usage: stamp-changelog.sh <vX.Y.Z> [changelog_file]
#
# Refreshing the Unreleased section is the wrong operation during a release: once
# the tag exists, `git cliff --unreleased` stops reporting the commits it covers,
# and an entry that only ever lived under Unreleased is dropped. `--tag` makes
# git-cliff treat the pending version as released instead, and the whole file is
# rebuilt from the tags and commits.

set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <vX.Y.Z> [changelog_file]" >&2
  exit 1
fi

# The version reaches git-cliff as a tag and grep as a pattern.
if ! tag="$("$(dirname "$0")/parse-version.sh" "$1")"; then
  exit 1
fi

changelog_file="${2:-CHANGELOG.md}"

if [ ! -f "$changelog_file" ]; then
  echo "Error: changelog file not found: $changelog_file" >&2
  exit 1
fi

if ! command -v git-cliff > /dev/null 2>&1; then
  echo "Error: git-cliff is required to update $changelog_file" >&2
  exit 1
fi

tmp_changelog="$(mktemp)"
trap 'rm -f "$tmp_changelog"' EXIT INT TERM HUP

# `--output` truncates before it writes, so it never points at the changelog.
git cliff --tag "$tag" --output "$tmp_changelog"

if [ ! -s "$tmp_changelog" ]; then
  echo "Error: git-cliff produced an empty changelog for $tag" >&2
  exit 1
fi

version="${tag#v}"
version_pattern="$(printf '%s' "$version" | sed 's/\./\\./g')"
if ! grep -q "^## \[${version_pattern}\]" "$tmp_changelog"; then
  echo "Error: no '## [${version}]' section in the regenerated changelog." >&2
  exit 1
fi

old_sections="$(grep -c '^## \[' "$changelog_file" || true)"
new_sections="$(grep -c '^## \[' "$tmp_changelog" || true)"
if [ "$new_sections" -lt "$old_sections" ]; then
  echo "Error: regeneration dropped sections ($old_sections -> $new_sections)." >&2
  exit 1
fi

# Which commits git-cliff reports changes between its versions, so every entry a
# released section holds must still be there afterwards. An entry is known by the
# commit SHA in its link, or by its text when it has none. Unreleased is left out,
# since stamping empties it into the new section.
if ! entry_guard="$(awk '
	function section_of(line) {
		if (match(line, /\[[^]]*\]/)) {
			return substr(line, RSTART + 1, RLENGTH - 2)
		}
		return ""
	}
	function identity_of(line) {
		if (match(line, /[0-9a-f]{40}/)) {
			return substr(line, RSTART, RLENGTH)
		}
		gsub(/^[ \t]+|[ \t]+$/, "", line)
		sub(/^-[ \t]+/, "", line)
		return "text:" line
	}
	function render(id) {
		if (id ~ /^text:/) {
			return substr(id, 6)
		}
		return substr(id, 1, 7)
	}
	NR == FNR {
		if ($0 ~ /^## \[/) {
			old_sec = section_of($0)
			if (old_sec == "Unreleased") {
				old_sec = ""
			} else if (!(old_sec in old_seen)) {
				old_seen[old_sec] = 1
				section_order[++sections] = old_sec
			}
			next
		}
		if (old_sec != "" && $0 ~ /^- /) {
			key = old_sec SUBSEP identity_of($0)
			if (!(key in old_count)) {
				entry_order[++entries] = key
			}
			old_count[key]++
		}
		next
	}
	{
		if ($0 ~ /^## \[/) {
			new_sec = section_of($0)
			if (new_sec == "Unreleased") {
				new_sec = ""
			} else {
				new_seen[new_sec] = 1
			}
			next
		}
		if (new_sec != "" && $0 ~ /^- /) {
			new_count[new_sec SUBSEP identity_of($0)]++
		}
	}
	END {
		for (i = 1; i <= sections; i++) {
			if (!(section_order[i] in new_seen)) {
				printf "section [%s] is missing from the regenerated changelog\n", section_order[i]
				bad = 1
			}
		}
		for (i = 1; i <= entries; i++) {
			key = entry_order[i]
			split(key, part, SUBSEP)
			if (!(part[1] in new_seen)) {
				continue
			}
			if (new_count[key] < old_count[key]) {
				printf "section [%s] lost a released entry: %s\n", part[1], render(part[2])
				bad = 1
			}
		}
		exit bad ? 1 : 0
	}
' "$changelog_file" "$tmp_changelog")"; then
  printf '%s\n' "$entry_guard" | sed 's/^/Error: /' >&2
  echo "Refusing a regeneration that loses released history." >&2
  exit 1
fi

# Written through the existing file, which keeps its permissions.
cat "$tmp_changelog" > "$changelog_file"

echo "Stamped $tag into $changelog_file"
