#!/bin/bash
# Publish a GitHub release for the version in backend/app/core/config.py.
#
#     scripts/release.sh            build, tag, push the tag, create the release
#     scripts/release.sh --dry-run  build the assets only and print where they are
#
# Release assets (installers and the in-app updater rely on these exact names):
#   depl0y.tar.gz        the source tree at HEAD plus a pre-built frontend/dist
#   SHA256SUMS           its sha256, checked by install.sh and /usr/local/sbin/depl0y-update
#   SHA256SUMS.minisig   minisign signature of SHA256SUMS, trusted comment "depl0y vX.Y.Z"
#
# Signing uses the secret key at $DEPL0Y_MINISIGN_KEY (default ~/.minisign/depl0y.key).
# If that key is password-protected, minisign asks for the password, so run it from a
# terminal; an unencrypted key (mode 0600) signs without a prompt. The matching public key is minisign.pub; install.sh and
# scripts/depl0y-update carry copies of it, and this script refuses to release if they differ.
#
# Needs git, npm, minisign and an authenticated gh (gh auth login).
set -euo pipefail

DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

cd "$(dirname "${BASH_SOURCE[0]}")/.."
die() { echo "❌ $*" >&2; exit 1; }

VERSION=$(grep -o 'return "[0-9]\+\.[0-9]\+\.[0-9]\+"' backend/app/core/config.py | grep -o '[0-9.]\+' | head -1)
[ -n "$VERSION" ] || die "no version in backend/app/core/config.py"
PKG_VERSION=$(python3 -c 'import json; print(json.load(open("frontend/package.json"))["version"])')
[ "$VERSION" = "$PKG_VERSION" ] || die "config.py says $VERSION but frontend/package.json says $PKG_VERSION"
TAG="v$VERSION"

PUBKEY=$(sed -n 2p minisign.pub)
[[ "$PUBKEY" =~ ^RW[A-Za-z0-9+/]{54}$ ]] || die "minisign.pub does not hold a minisign public key"
for f in scripts/depl0y-update install.sh; do
    grep -qxF "MINISIGN_PUBKEY=\"$PUBKEY\"" "$f" || die "$f does not carry the key in minisign.pub"
done
SECRET_KEY_FILE="${DEPL0Y_MINISIGN_KEY:-$HOME/.minisign/depl0y.key}"

if [ "$DRY_RUN" = false ]; then
    git diff --quiet && git diff --cached --quiet || die "uncommitted changes; commit first"
    [ "$(git rev-parse --abbrev-ref HEAD)" = main ] || die "not on main"
    git fetch -q origin main
    [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || die "HEAD is not origin/main; push first"
    git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && die "tag $TAG already exists"
    gh auth status >/dev/null 2>&1 || die "gh is not logged in"
    command -v minisign >/dev/null || die "minisign is not installed (sudo apt-get install minisign)"
    [ -f "$SECRET_KEY_FILE" ] || die "no signing key at $SECRET_KEY_FILE (set DEPL0Y_MINISIGN_KEY)"
    [ "$(stat -c %a "$SECRET_KEY_FILE")" = 600 ] || die "$SECRET_KEY_FILE must be mode 0600"
    # Bytes 2-3 of a minisign secret key name its KDF: "Sc" (scrypt) means password-protected.
    if [ "$(sed -n 2p "$SECRET_KEY_FILE" | base64 -d 2>/dev/null | head -c 4 | tail -c 2 | od -An -tx1 | tr -d ' \n')" = 5363 ] \
        && [ ! -t 0 ]; then
        die "the signing key is password-protected: run this from a terminal"
    fi
fi

OUT=$(mktemp -d)
# Remove the build directory however the script ends (a failure, Ctrl-C, or success).
# --dry-run turns this off before exiting, to leave the assets for inspection.
trap 'rm -rf "$OUT"' EXIT
TREE="$OUT/tree"
mkdir -p "$TREE"
echo "📦 Exporting HEAD..."
git archive --format=tar HEAD | tar -x -C "$TREE"

echo "🎨 Building frontend..."
(cd "$TREE/frontend" && npm ci --no-audit --no-fund --silent && npm run build --silent)
rm -rf "$TREE/frontend/node_modules"
[ -f "$TREE/frontend/dist/index.html" ] || die "frontend build produced no dist/index.html"

echo "🗜  Packing depl0y.tar.gz..."
tar -czf "$OUT/depl0y.tar.gz" --owner=0 --group=0 --numeric-owner --sort=name -C "$TREE" .
(cd "$OUT" && sha256sum depl0y.tar.gz > SHA256SUMS)
rm -rf "$TREE"
echo "   $(cat "$OUT/SHA256SUMS")"

if [ "$DRY_RUN" = true ]; then
    trap - EXIT
    echo "✅ Dry run: assets are in $OUT (not signed)"
    exit 0
fi

echo "🔏 Signing SHA256SUMS..."
minisign -S -s "$SECRET_KEY_FILE" -m "$OUT/SHA256SUMS" -x "$OUT/SHA256SUMS.minisig" \
    -c "Depl0y $TAG" -t "depl0y $TAG" \
    || die "signing failed (wrong password?). Nothing was tagged or published; run this again."
SIG_OUT=$(minisign -V -P "$PUBKEY" -m "$OUT/SHA256SUMS" -x "$OUT/SHA256SUMS.minisig" 2>&1) \
    || die "the signature does not verify against minisign.pub (wrong secret key?)"
[ "$(sed -n 's/^Trusted comment: //p' <<<"$SIG_OUT")" = "depl0y $TAG" ] || die "unexpected trusted comment"
echo "✓ Signature verifies against minisign.pub"

# Release notes: this version's CHANGELOG section.
awk -v v="## [$VERSION]" 'index($0, v) == 1 {p = 1; next} p && /^## \[/ {exit} p' CHANGELOG.md > "$OUT/notes.md"
[ -s "$OUT/notes.md" ] || die "no CHANGELOG.md entry for $VERSION"

echo "🏷  Tagging $TAG and publishing..."
git tag -a "$TAG" -m "Depl0y $VERSION"
git push -q origin "$TAG"
gh release create "$TAG" "$OUT/depl0y.tar.gz" "$OUT/SHA256SUMS" "$OUT/SHA256SUMS.minisig" \
    --title "Depl0y $VERSION" --notes-file "$OUT/notes.md" --latest
echo "✅ Released $TAG"
