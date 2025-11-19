# Changelog

All notable changes to Depl0y will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-11-19

### Added
- Fast fresh installs using pre-built frontend from package
- Installation now completes in ~30 seconds instead of 5+ minutes
- Automatic backend restart after upgrades
- Updates apply immediately without manual intervention

### Changed
- Fresh installs now use pre-built frontend by default
- Removed npm build step during installation for speed

### Fixed
- Installation no longer hangs during frontend build

## [1.1.9] - 2025-11-19

### Added
- Automatic backend restart after system upgrades
- Backend automatically loads new code after update completes

### Fixed
- Backend now properly restarts and loads new code after updates
- No more manual restart needed after applying updates

## [1.1.8] - 2025-11-19

### Fixed
- JavaScript error preventing Settings page from loading (version not defined)
- Installer version mismatch (was setting 1.1.7 instead of 1.1.8)
- Updates now work correctly in one step (no more multiple updates needed)

## [1.1.7] - 2025-11-18

### Added
- System Updates section now shows loading and error states
- Better error messages when update check fails

### Fixed
- No more blank screen when checking for updates
- Update section always displays status information

## [1.1.6] - 2025-11-18

### Added
- Version display now shows actual version from API
- Longer page reload delay (25s) after updates for backend restart

### Fixed
- Version no longer hardcoded as 1.0.0 in Settings page
- Updates have more time to complete before page reload

## [1.1.5] - 2025-11-17

### Added
- One-click automatic updates from Settings page
- Fast 30-second upgrades with pre-built frontend
- Update mechanism with process detachment using 'at' daemon
- Automatic cache clearing during upgrades
- Sudo permissions for update wrapper script

### Changed
- Installer now uses pre-built frontend during upgrades
- Update process completely automated from Settings UI

### Fixed
- Update mechanism now properly detaches from backend service
- Backend service survives during update process
- Python cache properly cleared after updates

## [1.1.0] - 2025-11-15

### Added
- Cloud Images support for ultra-fast VM deployment
- Automated cloud image template creation
- One-click cloud image setup from Settings
- Inter-node SSH configuration for Proxmox clusters
- Real-time deployment progress tracking
- High Availability (HA) management
- Bug report system with email notifications
- System logs viewer in Settings
- In-app documentation browser
- 2FA (TOTP) authentication support
- User role management (Admin, Operator, Viewer)
- Dashboard with real-time resource monitoring

### Changed
- Improved VM deployment workflow
- Enhanced error messages and validation
- Better storage validation for VM creation

### Fixed
- Node-specific template VMID handling
- Encryption key generation and validation
- Various UI/UX improvements

## [1.0.0] - 2025-11-01

### Added
- Initial release
- VM deployment from ISO images
- Proxmox VE integration
- Multi-host support
- ISO image management
- User authentication
- RESTful API
- Vue.js frontend
- SQLite database
- Nginx reverse proxy
