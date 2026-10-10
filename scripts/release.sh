#!/bin/bash
# Publish a GitHub release for the version in backend/app/core/config.py.
#
#     scripts/release.sh            build, tag, push the tag, create the release
#     scripts/release.sh --dry-run  build the assets only and print where they are
#
# Release assets (installers and the in-app updater rely on these exact names):
#   depl0y.tar.gz  the source tree at HEAD plus a pre-built frontend/dist
#   SHA256SUMS     its sha256, checked by install.sh and /usr/local/sbin/depl0y-update
#
# Needs git, npm and an authenticated gh (gh auth login).
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

if [ "$DRY_RUN" = false ]; then
    git diff --quiet && git diff --cached --quiet || die "uncommitted changes; commit first"
    [ "$(git rev-parse --abbrev-ref HEAD)" = main ] || die "not on main"
    git fetch -q origin main
    [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || die "HEAD is not origin/main; push first"
    git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && die "tag $TAG already exists"
    gh auth status >/dev/null 2>&1 || die "gh is not logged in"
fi

OUT=$(mktemp -d)
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
    echo "✅ Dry run: assets are in $OUT"
    exit 0
fi

# Release notes: this version's CHANGELOG section.
awk -v v="## [$VERSION]" 'index($0, v) == 1 {p = 1; next} p && /^## \[/ {exit} p' CHANGELOG.md > "$OUT/notes.md"
[ -s "$OUT/notes.md" ] || die "no CHANGELOG.md entry for $VERSION"

echo "🏷  Tagging $TAG and publishing..."
git tag -a "$TAG" -m "Depl0y $VERSION"
git push -q origin "$TAG"
gh release create "$TAG" "$OUT/depl0y.tar.gz" "$OUT/SHA256SUMS" \
    --title "Depl0y $VERSION" --notes-file "$OUT/notes.md" --latest
rm -rf "$OUT"
echo "✅ Released $TAG"
