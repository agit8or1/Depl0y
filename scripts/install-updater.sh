#!/bin/bash
# Install Depl0y's privileged updater and sudo rules. Run as root from a Depl0y
# release or checkout:
#
#     sudo bash scripts/install-updater.sh
#
# Called by install.sh. Existing installs run it once to move to the new updater;
# after that, /usr/local/sbin/depl0y-update keeps both files current.
set -euo pipefail
umask 022

[ "$(id -u)" = 0 ] || { echo "Run as root: sudo bash $0" >&2; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

visudo -cqf "$HERE/sudoers.depl0y" || { echo "❌ $HERE/sudoers.depl0y failed visudo" >&2; exit 1; }
bash -n "$HERE/depl0y-update" || { echo "❌ $HERE/depl0y-update has a syntax error" >&2; exit 1; }

install -m 0755 -o root -g root "$HERE/depl0y-update" /usr/local/sbin/depl0y-update.new
mv -f /usr/local/sbin/depl0y-update.new /usr/local/sbin/depl0y-update

install -m 0440 -o root -g root "$HERE/sudoers.depl0y" /etc/sudoers.d/.depl0y.new
mv -f /etc/sudoers.d/.depl0y.new /etc/sudoers.d/depl0y
visudo -cq || { echo "❌ sudoers no longer parses; check /etc/sudoers.d/depl0y" >&2; exit 1; }

echo "✓ Installed /usr/local/sbin/depl0y-update and /etc/sudoers.d/depl0y"
