#!/bin/bash
# Bridge from the old in-app updater (Depl0y 2.2.89 and earlier) to the new one.
#
# Old versions download the release source to /tmp/depl0y-update and run this file
# from there as the depl0y user. From 2.2.90 on, updates are done by the root-owned
# /usr/local/sbin/depl0y-update instead; this script installs it if it can, hands
# over, and follows its log so the old progress view still shows what happens.
set -uo pipefail

EXTRACT_DIR="${1:-/tmp/depl0y-update}"
UPDATER=/usr/local/sbin/depl0y-update
NEW_LOG=/var/log/depl0y-update/update.log

echo "🔄 Switching to the new Depl0y updater..."

if [ ! -x "$UPDATER" ] || ! sudo -n -l "$UPDATER" apply >/dev/null 2>&1; then
    # Installs whose sudoers was widened by hand still allow root rsync. Use it once to
    # install the updater and the new sudo rules, which remove that access.
    if sudo -n -l /usr/bin/rsync --version >/dev/null 2>&1 \
        && visudo -cqf "$EXTRACT_DIR/scripts/sudoers.depl0y" \
        && bash -n "$EXTRACT_DIR/scripts/depl0y-update"; then
        echo "🔐 Installing $UPDATER and new sudo rules..."
        sudo -n /usr/bin/rsync --chmod=F0755 --chown=root:root \
            "$EXTRACT_DIR/scripts/depl0y-update" "$UPDATER" || { echo "❌ Could not install $UPDATER"; exit 1; }
        sudo -n /usr/bin/rsync --chmod=F0440 --chown=root:root \
            "$EXTRACT_DIR/scripts/sudoers.depl0y" /etc/sudoers.d/depl0y || { echo "❌ Could not install sudo rules"; exit 1; }
    else
        echo "❌ One-time manual step needed to finish this update."
        echo "   On the Depl0y server, as root, run:"
        echo "     sudo bash $EXTRACT_DIR/scripts/install-updater.sh"
        echo "   then click Update again."
        exit 1
    fi
fi

sudo -n "$UPDATER" apply || { echo "❌ Could not start $UPDATER"; exit 1; }

# Follow the new log until the update finishes (at most 20 minutes).
for _ in $(seq 1 600); do
    if [ -r "$NEW_LOG" ] && grep -qE 'Upgrade complete|❌' "$NEW_LOG"; then break; fi
    sleep 2
done
cat "$NEW_LOG" 2>/dev/null
