#!/usr/bin/env bash
# Historical first-publication helper. The repository now exists: use clone/branches.
# Never makes a public repo; refuses any existing local history or remote.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OWNER="fokhruli"
REPO="BnTeX"
TARGET="$OWNER/$REPO"
export GH_HOST=github.com
for cmd in gh git python3; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd; install it first." >&2; exit 1; }
done
gh auth status --hostname github.com >/dev/null
LOGIN="$(gh api --hostname github.com user --jq .login)"
[[ "$LOGIN" == "$OWNER" ]] || { echo "Authenticated as $LOGIN; expected $OWNER. No changes made." >&2; exit 1; }
# Refuse existing local history/remotes: this helper is only for the initial archive.
if [[ -e .git ]]; then
  [[ -d .git ]] || { echo 'Refusing a worktree/submodule gitfile.' >&2; exit 1; }
  [[ "$(git rev-parse --show-toplevel)" == "$ROOT" ]] || exit 1
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    echo 'This repository already has commits. Review and publish it manually; no changes made.' >&2; exit 1
  fi
  [[ -z "$(git remote)" ]] || { echo 'Existing remote; refusing to reuse it.' >&2; exit 1; }
elif git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo 'This directory is inside another Git repository. Move the extracted archive first.' >&2; exit 1
fi
NAME="$(git config user.name || true)"
EMAIL="$(git config user.email || true)"
[[ -n "$NAME" && -n "$EMAIL" ]] || {
  echo 'Configure your Git author name/email, then rerun. No remote was created.' >&2; exit 1;
}
python3 tools/audit_release.py
if [[ ! -d .git ]]; then git init -b main; fi
git add -- .
python3 tools/audit_release.py
git commit -m 'Initial BnTeX native-glyph prototype, validation, and development plan'
# Creation is atomic on GitHub: an existing name fails here and is never reused.
gh repo create "$TARGET" --private --description \
  'Experimental Bengali typesetting for pdfLaTeX: native glyph backend and native-shaper development'
VISIBILITY="$(gh repo view "$TARGET" --json isPrivate --jq .isPrivate)"
[[ "$VISIBILITY" == true ]] || {
  echo 'Private visibility could not be confirmed. No source has been pushed.' >&2; exit 1;
}
REMOTE_OWNER="$(gh repo view "$TARGET" --json owner --jq .owner.login)"
[[ "$REMOTE_OWNER" == "$OWNER" ]] || { echo 'Owner mismatch. No source pushed.' >&2; exit 1; }
URL="$(gh repo view "$TARGET" --json url --jq .url)"
gh auth setup-git --hostname github.com
git remote add origin "$URL.git"
git push -u origin main
[[ "$(gh repo view "$TARGET" --json isPrivate --jq .isPrivate)" == true ]] || {
  echo 'Unexpected visibility result after push; review repository settings immediately.' >&2; exit 1;
}
printf '\nCreated and pushed PRIVATE repository: %s\n' "$URL"
