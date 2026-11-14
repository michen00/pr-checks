#!/usr/bin/env bash
#
# Posts the findings the check action recorded as one comment on the pull request,
# the errors first and then the warnings. The comment is edited as the findings change
# and deleted once there are none. Only a bot's comment that starts with the marker is
# edited or deleted, so a person quoting the marker is left alone.
#
# Environment: GH_TOKEN, REPO, HEAD_SHA, HEAD_REPO, HEAD_BRANCH, FINDINGS_DIR, MARKER,
# HANDOFF.

set -euo pipefail

readonly FORMAT=1

# GitHub refuses a longer comment body. Counted in bytes, which cuts early, not late.
readonly BODY_MAX=65536

readonly TRUNCATION_NOTICE='**The findings are cut off here.** GitHub limits how long a comment may be. The check job log and its findings artifact hold every finding.'

# A run that did not finish writes no format file, and a later major version may write
# another number; either way this run cannot read the findings.
format="$(cat "${FINDINGS_DIR}/format" 2> /dev/null || true)"
if [ "${format}" != "${FORMAT}" ]; then
  echo "::warning::the findings are not in format ${FORMAT}, so the comment is unchanged"
  exit 0
fi

if ! [[ ${HEAD_SHA} =~ ^[0-9a-f]{40}$ ]]; then
  echo "::error::not a commit SHA: ${HEAD_SHA}"
  exit 1
fi

# From the API, not the artifact, which the pull request's own run uploaded. Matching
# the run's head commit, repository and branch keeps a fork's pull request from aiming
# the comment at another made from the same commit.
matches="$(gh api "repos/${REPO}/commits/${HEAD_SHA}/pulls" |
  jq -c --arg sha "${HEAD_SHA}" --arg repo "${HEAD_REPO}" --arg branch "${HEAD_BRANCH}" \
    '[.[] | select(.state == "open" and .head.sha == $sha
        and .head.repo.full_name == $repo and .head.ref == $branch) | .number]')"
case "$(jq 'length' <<< "${matches}")" in
  0)
    echo "no open pull request has this run's head, so there is nothing to comment on"
    exit 0
    ;;
  1) pr_number="$(jq -r '.[0]' <<< "${matches}")" ;;
  *)
    echo "::warning::more than one open pull request has this run's head; commenting on none"
    exit 0
    ;;
esac
if ! [[ ${pr_number} =~ ^[1-9][0-9]*$ ]]; then
  echo "::error::not a pull request number: ${pr_number}"
  exit 1
fi

# A finding can quote the author, so it renders as text in one list item: no HTML, link,
# block, mention or issue reference. `&` goes first; later rules add ampersands.
zero_width_space="$(printf '\342\200\213')"
readonly zero_width_space
escape_for_markdown() {
  tr -d '\r\v\f' |
    sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/[][`*_~#\\]/\\&/g' \
      -e "s/[@#]/&${zero_width_space}/g"
}

body_file="$(mktemp)"
findings_file="$(mktemp)"
handoff_file="$(mktemp)"
list_file="$(mktemp)"
readonly body_file findings_file handoff_file list_file
trap 'rm -f "${body_file}" "${findings_file}" "${handoff_file}" "${list_file}"' EXIT

# Appends a heading, a sentence, then each file's findings under the file's name, which
# is the check's. Prints whether it wrote anything, so an empty section has no heading.
render_section() {
  local dir="$1" heading="$2" lead="$3" wrote=false file name
  for file in "${dir}"/*.txt; do
    [ -s "${file}" ] || continue
    if [ "${wrote}" = false ]; then
      printf '### %s\n\n%s\n\n' "${heading}" "${lead}" >> "${findings_file}"
      wrote=true
    fi
    name="$(basename "${file}" .txt | escape_for_markdown)"
    {
      printf '**%s**\n\n' "${name}"
      while IFS= read -r line; do
        printf -- '- %s\n' "$(printf '%s' "${line}" | escape_for_markdown)"
      done < "${file}"
      printf '\n'
    } >> "${findings_file}"
  done
  printf '%s' "${wrote}"
}

printf '%s\n' "${MARKER}" > "${body_file}"
errors_found="$(render_section "${FINDINGS_DIR}/errors" 'Why the checks failed' \
  '**These block the merge.** Fix each one; the checks run again on the next push or edit.')"
warnings_found="$(render_section "${FINDINGS_DIR}/warnings" 'Advisory findings' \
  '**These do not block.** Each takes a judgment, so the decision is yours, and leaving one as it is can be the right answer.')"

found=false
if [ "${errors_found}" = true ] || [ "${warnings_found}" = true ]; then
  found=true
fi

# Names the pull request rather than the comment, which has no id yet when created, and
# asks for a decision on each warning rather than a fix.
if [ "${found}" = true ] && [ "${HANDOFF}" = true ]; then
  {
    printf '<details>\n<summary>Hand these to a coding agent</summary>\n\n'
    printf '```text\n'
    printf 'The PR checks on %s#%s left findings in a comment. Read them with:\n' \
      "${REPO}" "${pr_number}"
    printf '  gh pr view %s --repo %s --comments\n' "${pr_number}" "${REPO}"
    if [ "${errors_found}" = true ]; then
      printf 'Fix every finding under the heading that says why the checks failed.\n'
    fi
    if [ "${warnings_found}" = true ]; then
      printf 'For each advisory finding, decide whether it is worth acting on, fix\n'
      printf 'the ones that are, and reply on the pull request saying which you\n'
      printf 'rejected and why.\n'
    fi
    printf '```\n\n'
    printf '</details>\n'
  } >> "${handoff_file}"
fi

# The findings get whatever room the fixed parts leave. A cut winds back to the last
# space, which keeps the body valid UTF-8 and spares the reader half a word.
notice=$'\n\n'"${TRUNCATION_NOTICE}"$'\n\n'
readonly notice
fixed=$(($(wc -c < "${body_file}") + $(wc -c < "${handoff_file}") + ${#notice}))
budget=$((BODY_MAX - fixed))
readonly fixed budget

if [ "$(wc -c < "${findings_file}")" -gt "${budget}" ]; then
  kept="$(head -c "${budget}" "${findings_file}")"
  printf '%s%s' "${kept% *}" "${notice}" >> "${body_file}"
else
  cat "${findings_file}" >> "${body_file}"
fi
cat "${handoff_file}" >> "${body_file}"

# Written to a file, not piped into `head`, so gh is never cut off by SIGPIPE when it
# finds more than one comment.
gh api "repos/${REPO}/issues/${pr_number}/comments" --paginate |
  jq -r --arg marker "${MARKER}" \
    '.[] | select(.user.type == "Bot") | select(.body | startswith($marker)) | .id' \
    > "${list_file}"
existing="$(head -n 1 "${list_file}")"

if [ "${found}" = true ]; then
  if [ -n "${existing}" ]; then
    gh api -X PATCH "repos/${REPO}/issues/comments/${existing}" -F "body=@${body_file}"
  else
    gh pr comment "${pr_number}" --repo "${REPO}" --body-file "${body_file}"
  fi
elif [ -n "${existing}" ]; then
  gh api -X DELETE "repos/${REPO}/issues/comments/${existing}"
fi
