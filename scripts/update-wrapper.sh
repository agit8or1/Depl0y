#!/bin/bash
# Depl0y Update Wrapper - Completely detaches installer from backend service
# This ensures the installer survives when it stops the backend

INSTALLER_PATH="$1"

if [ -z "$INSTALLER_PATH" ]; then
    echo "ERROR: No installer path provided"
    exit 1
fi

if [ ! -f "$INSTALLER_PATH" ]; then
    echo "ERROR: Installer not found at $INSTALLER_PATH"
    exit 1
fi

# Use 'at' to schedule the installer to run immediately but completely detached
# The 'at' daemon will run the job in its own process tree, independent of the backend service
# IMPORTANT: Must run with sudo since installer needs root permissions
echo "/usr/bin/sudo /bin/bash $INSTALLER_PATH > /tmp/depl0y-update.log 2>&1" | /usr/bin/at now 2>&1

if [ $? -eq 0 ]; then
    echo "Update scheduled successfully via 'at' daemon"
    echo "The installer will run independently and survive backend restarts"
    exit 0
else
    echo "ERROR: Failed to schedule update"
    exit 1
fi
