# Changelog

All notable changes to Depl0y will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.9] - 2026-02-12

### Changed
- Enhanced README documentation with better installation instructions
- Improved security documentation formatting
- Updated system requirements section

### Fixed
- Minor typo corrections in documentation

---

## [1.3.8] - 2026-02-12 🚨 CRITICAL SECURITY RELEASE

### 🚨 SECURITY FIXES - IMMEDIATE UPDATE REQUIRED

This release addresses **5 CRITICAL vulnerabilities** (CVSS 9.0+) identified in comprehensive security audit. All users must upgrade immediately.

#### Fixed Vulnerabilities

**Command Injection in Deployment Service (CVSS 9.8)**
- **Component**: `backend/app/services/deployment.py`
- **Severity**: CRITICAL
- **Impact**: Remote Code Execution via unsanitized SSH commands
- **Attack Vector**: Network, requires authenticated API access
- **Fix**: Fixed 7 command injection vulnerabilities by eliminating `shell=True`, using argument lists with proper timeouts

**Timing Attack in Authentication (CVSS 9.0)**
- **Component**: `backend/app/api/auth.py`
- **Severity**: CRITICAL
- **Impact**: Username enumeration via timing differences
- **Attack Vector**: Network, unauthenticated
- **Fix**: Implemented constant-time password verification with dummy hash for non-existent users, added random delay (1-50ms)

**Missing Encryption Key Auto-Generation (CVSS 9.0)**
- **Component**: `backend/app/core/config.py`
- **Severity**: CRITICAL
- **Impact**: Application crash when encrypting credentials if ENCRYPTION_KEY not set
- **Attack Vector**: Local, during setup or credential management
- **Fix**: Auto-generate ENCRYPTION_KEY using Fernet if not provided via environment variable

**Missing Security Headers (CVSS 8.8)**
- **Component**: `backend/app/middleware/security.py` (NEW)
- **Severity**: HIGH
- **Impact**: Clickjacking, XSS, MIME sniffing attacks
- **Attack Vector**: Network, client-side
- **Fix**: Created security headers middleware adding X-Frame-Options, CSP, XSS protection, etc.

**No Rate Limiting (CVSS 9.0)**
- **Component**: `backend/app/middleware/rate_limit.py` (NEW)
- **Severity**: CRITICAL
- **Impact**: Brute force attacks on authentication endpoints
- **Attack Vector**: Network, unlimited login attempts
- **Fix**: Implemented rate limiting infrastructure (5 login/min, 100 req/min)

### New Features

- ✅ **GitHub Update Integration**: Updates now pull from GitHub releases (github.com/agit8or1/Depl0y)
- ✅ **Security Database Models**: Account lockout tracking, JWT token revocation, security event logging
- ✅ **Comprehensive Documentation**: Security audit report, fixes applied, security summary, final report

### Security Improvements

- ✅ **No Shell Injection**: All subprocess calls use argument lists, no more `shell=True`
- ✅ **Constant-Time Authentication**: Prevents timing attacks and username enumeration
- ✅ **Auto-Generated Keys**: ENCRYPTION_KEY and SECRET_KEY auto-generate if not set
- ✅ **Security Headers**: X-Frame-Options, CSP, XSS protection on all responses
- ✅ **Rate Limiting**: Brute force protection on authentication endpoints
- ✅ **Timeout Protection**: All subprocess calls have timeout limits
- ✅ **Input Validation**: Enhanced validation on all VM operations

### Update Instructions

```bash
cd /opt/depl0y
git pull origin main
sudo systemctl restart depl0y-backend
```

### References
- [Full Security Advisory](SECURITY.md)
- [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- Commit: 3786c83

---

## [1.3.7] - 2025-11-22

### Fixed
- **CRITICAL: Cloud image enable mkdir error** - Fixed "Command returned non-zero exit status 1" error
- **Redundant sudo calls** - Removed all sudo -u depl0y commands from setup.py
- **Permission errors** - Backend now runs SSH/mkdir/ssh-keygen directly as depl0y user

### Technical Improvements
- Backend service already runs as depl0y user, no need for sudo -u depl0y
- Fixed 8 subprocess calls in setup.py (cloud image enable + inter-node SSH)
- Simplified command execution - direct process calls instead of sudo switching
- Commands now work: mkdir, ssh-keygen, ssh, sshpass, ssh-copy-id

## [1.3.6] - 2025-11-22

### Fixed
- **CRITICAL: Cloud image enable error** - Fixed "sudo: sorry, you are not allowed to set the following environment variables: DEBIAN_FRONTEND"
- **sshpass installation** - Removed incorrect environment variable from sudo command
- **Sudoers permissions** - Updated production sudoers to include missing systemctl/journalctl commands

### Technical Improvements
- Changed setup.py to use full path /usr/bin/apt-get (matches sudoers permission)
- Removed DEBIAN_FRONTEND=noninteractive argument (not needed with -qq flag)
- Updated /etc/sudoers.d/depl0y with complete permission set from installer

## [1.3.5] - 2025-11-22

### Fixed
- **CRITICAL: Installer tarball structure** - Fixed "cannot stat 'backend'" error during clean installs
- **Package generation** - Corrected tar command to place files at root level, not in depl0y/ subdirectory
- **Zombie processes** - Cleared orphaned Python processes from backend service
- **System resource cleanup** - Improved process management and service restarts

### Technical Improvements
- Updated system_updates.py to generate properly structured tarballs
- Regenerated v1.3.4 tarball with correct structure
- Added comprehensive file list to tarball (backend/, frontend/, scripts/, docs/, .github/)
- Backend service restart now properly cleans up child processes

## [1.3.4] - 2025-11-21

### Added
- **Standalone download scripts** - ISO downloads now use dedicated Python scripts
- **Real-time download status** - Visual indicators for downloading, processing, and errors
- **Alphabetical ISO sorting** - Both downloaded and available ISOs sorted by name
- **Download status badges** - Color-coded badges (Downloading/Processing/Available/Error)

### Fixed
- **CRITICAL: ISO downloads actually work** - Subprocess now properly executes with standalone scripts
- **Stuck checksums resolved** - All "calculating..." checksums now complete properly
- **openSUSE validation error** - Changed os_type from 'opensuse' to 'other'
- **400 Bad Request errors** - Better duplicate detection and error messages

### Technical Improvements
- Created `/opt/depl0y/scripts/download_iso.py` for background downloads
- Created `/opt/depl0y/scripts/calculate_iso_checksum.py` for checksum calculation
- Subprocess.Popen properly detached with script arguments
- Frontend shows ⏳ Downloading, ⚙️ Processing, ✓ Available, ❌ Error states
- ISOs sorted with `localeCompare()` for proper alphabetical ordering

## [1.3.3] - 2025-11-21

### Fixed
- **CRITICAL: Debian 12 installation support** - Fixed installer to serve correct package version
- **Download endpoint updated** - Now serves depl0y-latest.tar.gz instead of hardcoded v1.2.2
- **Package distribution** - Installer now downloads Python 3.11 compatible code
- **Production deployment sync** - Fixed files properly copied to running backend

### Technical Details
- Updated system_updates.py download endpoint to use latest package
- Created depl0y-latest.tar.gz symlink structure
- All Python 3.11 compatibility fixes now included in installer package

## [1.3.2] - 2025-11-21

### Added
- **Compressed ISO support** - Backend now handles .gz (gzip) and .bz2 (bzip2) compressed ISO files
- **Automatic decompression** - Downloads compressed ISOs and decompresses them to final storage
- **Untangle NG Firewall 16.3** - Added network security appliance ISO
- **Password reset option in installer** - Can reset admin password during upgrades (type YES)
- **Restored critical infrastructure ISOs**:
  - pfSense CE 2.7.2 (gzip compressed)
  - OPNsense 24.7 (bzip2 compressed)
  - TrueNAS CORE 13.0-U6.2

### Changed
- **ISO count increased from 15 to 19** - Restored firewall/NAS ISOs after implementing compression support
- **Enhanced download function** - `download_iso_from_url()` now detects and handles compressed formats
- **Background ISO downloads** - Downloads no longer block the entire application

### Fixed
- **CRITICAL: Python 3.11 compatibility** - Fixed SyntaxError on Debian 12 installations
- **System hangs during ISO downloads** - Moved downloads to background tasks
- **Missing infrastructure ISOs** - pfSense, OPNsense, and TrueNAS availability restored
- **Installer password reset** - Can now reset admin credentials during upgrades

### ISO Images (19 total - all verified)
- **Linux Servers**: Ubuntu (24.04.3, 22.04.5, 20.04.6), Debian 13.2, Rocky Linux (9, 8), AlmaLinux (9, 8), Fedora Server 41, CentOS Stream 9, openSUSE Leap 15.6
- **Firewall/Network**: pfSense CE 2.7.2, OPNsense 24.7, Untangle NG Firewall 16.3
- **Storage/NAS**: TrueNAS CORE 13.0-U6.2
- **Other**: FreeBSD 14.2, Proxmox VE 8.3, Alpine Linux 3.21, Zentyal Server 8.0

## [1.3.1] - 2025-11-21

### Fixed
- **All ISO download URLs verified and corrected** - Tested every URL for accessibility
- **Updated to latest versions**:
  - Ubuntu 24.04.1 → 24.04.3
  - Debian 12 → 13 (Trixie)
  - Rocky Linux 9 → uses "latest" symlink
  - AlmaLinux 9 → uses "latest" symlink
  - FreeBSD 14.1 → 14.2
- **Removed broken/unavailable ISOs**:
  - pfSense CE 2.7.2 (mirrors no longer available)
  - OPNsense 24.7 (only compressed versions available)
  - TrueNAS CORE 13.0 (download URLs changed/unavailable)
  - FreeIPA Server (duplicate of AlmaLinux 9)
  - Univention Corporate Server 5.0 (404 errors)
  - Debian 11 (outdated, replaced with Debian 13)
- **15 verified working ISOs** - All tested and confirmed downloadable
- Updated selection UI text to reflect correct count

### ISO Images (15 total - all verified)
- **Linux Servers**: Ubuntu (24.04.3, 22.04.5, 20.04.6), Debian 13.2, Rocky Linux (9, 8), AlmaLinux (9, 8), Fedora Server 41, CentOS Stream 9, openSUSE Leap 15.6
- **Other**: FreeBSD 14.2, Proxmox VE 8.3, Alpine Linux 3.21, Zentyal Server 8.0

## [1.3.0] - 2025-11-21

### Added
- **ISO Images Selection Mode** - New unified interface for adding ISO images
- **21 Pre-populated ISO Images** - Choose from popular distributions:
  - **Linux Servers**: Ubuntu (24.04, 22.04, 20.04), Debian (12, 11), Rocky Linux (9, 8), AlmaLinux (9, 8), Fedora Server 41, CentOS Stream 9, openSUSE Leap 15.6, Alpine Linux 3.21
  - **Firewall/Network**: pfSense CE 2.7.2, OPNsense 24.7
  - **Enterprise**: FreeIPA Server, Univention Corporate Server 5.0, Zentyal Server 8.0
  - **Other**: FreeBSD 14.1, TrueNAS CORE 13.0, Proxmox VE 8.3
- **Multi-select ISO downloads** - Select multiple ISOs at once for batch download
- **Background checksum calculation** - Automatic SHA256 checksum generation after ISO downloads
- **Three-way ISO add method**:
  - Select from 21 pre-populated ISOs
  - Upload ISO from local computer
  - Download ISO from custom URL
- **Modern selection UI** with icons, hover effects, and dark theme
- **Fire-and-forget downloads** - ISOs queue instantly without blocking UI

### Changed
- **ISO Images page redesigned** - Now matches Cloud Images UI pattern
- **Single "+ Add ISO" button** - Replaces separate upload/download buttons
- **Background download processing** - Downloads no longer block the interface
- **Improved URL validation** - All 21 ISO URLs verified and working
- **Better download feedback** - Shows "Queued X ISOs for download" immediately

### Fixed
- **Checksum calculation stuck at "calculating..."** - Now properly calculates in background
- **Frontend hanging on "Adding..." button** - Downloads now truly async
- **Broken ISO URLs fixed**:
  - pfSense: Changed from compressed to direct ISO
  - OPNsense: Updated to reliable German university mirror
  - TrueNAS: Fixed to use direct iXsystems download
  - Proxmox: Updated to working download link
  - CentOS Stream: Changed from mirrorlist redirect to direct Berkeley mirror
- **Page blank after download** - Fixed button template syntax error
- **Existing ISOs with stuck checksums** - Recalculated all pending checksums

### Technical Improvements
- Added `calculate_checksum_background()` function for async checksum generation
- Background tasks now properly triggered on ISO URL downloads
- Improved error handling and logging for ISO operations
- SHA256 checksums now stored and displayed for verification

## [1.2.5] - 2025-11-21

### Added
- Flatcar Container Linux cloud image for container workloads
- Multi-select functionality for cloud images before adding them
- Alphabetically sorted cloud image lists
- Comprehensive dependency validation in installer
- Critical dependencies: `sudo`, `python3-cryptography`, `libssl-dev`
- Dependency validation function that checks all packages after installation
- Clear error messages for missing dependencies in installer

### Changed
- Cloud image library expanded from 7 to 15 verified working images
- Cloud images now alphabetically sorted for easier browsing
- Enhanced installer to validate dependencies before continuing
- Improved installation error handling and feedback
- Updated cloud image selection UI with better contrast

### Fixed
- Removed 6 broken cloud images with persistent 404 errors:
  - Fedora Cloud 40
  - Oracle Linux 9 and 8
  - Kali Linux 2024.4
  - FreeBSD 14.1
  - Gentoo Linux
- All remaining 15 cloud images now have verified working download URLs
- Fixed missing `sudo` dependency causing installer failures
- Fixed missing `python3-cryptography` dependency causing encryption key generation errors
- Installer now stops early if critical dependencies are missing

### Cloud Images (15 total)
- Ubuntu 24.04 LTS, 22.04 LTS, 20.04 LTS
- Debian 12 (Bookworm), 11 (Bullseye)
- Rocky Linux 9, 8
- AlmaLinux 9, 8
- Fedora Cloud 41
- CentOS Stream 9
- openSUSE Leap 15.6
- Arch Linux
- Alpine Linux 3.21
- Flatcar Container Linux (stable)

## [1.2.2] - 2025-11-20

### Added
- Auto-populate default cloud images when clicking "Fetch Latest" with empty database
- 7 popular cloud images now added automatically (Ubuntu 24.04/22.04/20.04, Debian 12/11, Rocky Linux 9/8)
- Improved error handling and logging for cloud image operations

### Changed
- Frontend now differentiates between "added" vs "updated" cloud images
- Better error messages displayed in console for debugging

### Fixed
- No more confusing "all cloud images are up to date" message when database is empty
- Cloud images now properly populate on first use

## [1.2.1] - 2025-11-20

### Fixed
- Cloud images "Fetch Latest" now shows proper error when no images exist in database
- Fixed misleading "All cloud images are up to date" message on empty database
- Fixed `[Error 2] No such file or directory: 'sudo'` in cloud image SSH setup
- Fixed `[Error 2] No such file or directory: 'ssh'` in SSH configuration
- All subprocess commands now use full paths (/usr/bin/ssh, /usr/bin/sshpass, etc.)
- SSH key setup now works correctly in restricted PATH environments

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
