# Depl0y

**Automated VM Deployment Panel for Proxmox VE**

Depl0y is a free, open-source web-based control panel that simplifies the deployment and management of virtual machines on Proxmox VE infrastructure. With an intuitive interface and powerful automation features, Depl0y makes VM provisioning accessible to everyone.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Vue.js](https://img.shields.io/badge/vue.js-3.x-green.svg)

## Features

### Core Functionality
- **Automated VM Deployment** - Deploy Ubuntu, Debian, CentOS, Rocky Linux, Alma Linux, and Windows VMs with a few clicks
- **⚡ Cloud Images** - Ultra-fast 30-second deployments using pre-configured OS images (Ubuntu, Debian)
- **Cloud-Init Integration** - Automatic configuration of Linux VMs with cloud-init
- **Multi-Hypervisor Support** - Manage multiple Proxmox VE hosts and clusters
- **Resource Management** - Real-time monitoring of CPU, memory, and disk usage across your infrastructure
- **ISO Management** - Upload, store, and manage OS installation images

### Advanced Features
- **Update Management** - One-click system updates for deployed Linux VMs
- **QEMU Guest Agent** - Automatic installation and configuration
- **SSH Access** - Built-in SSH key management and password-based authentication
- **Network Configuration** - Static IP or DHCP configuration with cloud-init
- **Partition Management** - Single large partition or custom schemes for Linux deployments

### Security & Access Control
- **Multi-User Support** - Role-based access control (Admin, Operator, Viewer)
- **2FA Authentication** - TOTP-based two-factor authentication
- **Encrypted Credentials** - All sensitive data is encrypted at rest
- **Audit Logging** - Track all user actions and system changes

### User Experience
- **Modern UI** - Responsive, beautiful interface built with Vue.js
- **Real-time Status** - Live VM status updates and resource monitoring
- **Dashboard Analytics** - Overview of your entire virtualization infrastructure
- **RESTful API** - Complete API for automation and integration

## Screenshots

### Dashboard
![Dashboard](screenshots/01-dashboard.png)
*Real-time overview of your infrastructure with resource usage, VM status, and quick actions*

### Virtual Machines Management
![VM List](screenshots/02-vm-list.png)
*Manage all your VMs with status monitoring and one-click controls*

### Easy VM Creation
![Create VM](screenshots/03-create-vm-basic.png)
*Intuitive VM creation wizard with cloud image support for 30-second deployments*

### Proxmox Cluster Management
![Proxmox Hosts](screenshots/06-proxmox-hosts.png)
*Monitor multiple Proxmox nodes and datacenters from a single interface*

### Cloud Images for Ultra-Fast Deployment
![Cloud Images](screenshots/08-cloud-images.png)
*Pre-configured OS images for instant VM deployment*

### High Availability Management
![HA Management](screenshots/10-ha-resources.png)
*Configure automatic VM failover for business continuity*

## Quick Start

### Prerequisites
- A server running Linux (Ubuntu 22.04+, Debian 11+, or similar)
- At least 2GB RAM and 20GB disk space
- Python 3.10+, Node.js 18+, and nginx
- Access to one or more Proxmox VE hosts

### One-Line Installation

The fastest way to install Depl0y is with the automated installer:

```bash
curl -fsSL http://deploy.agit8or.net/downloads/install.sh | sudo bash
```

This will:
- Install all dependencies (Python, Node.js, nginx, SQLite)
- Set up the Depl0y backend and frontend
- Create a systemd service for automatic startup
- Configure nginx as a reverse proxy
- Complete in approximately 30 seconds

### Post-Installation

1. **Access the web interface**
   - Open your browser and navigate to `http://your-server-ip`
   - Default credentials: `admin` / `admin`
   - **IMPORTANT**: Change the default password immediately!

2. **Enable 2FA (Recommended)**
   - Go to "User Profile" and enable TOTP authentication
   - Scan the QR code with your authenticator app

3. **Add your first Proxmox host**
   - Go to "Proxmox Hosts" in the sidebar
   - Click "Add Host" and enter your Proxmox credentials
   - Test the connection

4. **Deploy your first VM**
   - Go to "Virtual Machines"
   - Click "Create VM"
   - Fill in the required information and deploy!

## Manual Installation

For manual installation or to review the installer script, see the [install.sh](install.sh) file or visit the [documentation](docs/).

## Configuration

### Environment Variables

The installer automatically configures environment variables during installation. For manual configuration, set:

```bash
# Security (automatically generated during installation)
SECRET_KEY=your_jwt_secret_key_minimum_32_chars
ENCRYPTION_KEY=your_fernet_encryption_key

# Database (default: SQLite)
DATABASE_URL=sqlite:////var/lib/depl0y/db/depl0y.db

# Application
DEBUG=false
LOG_LEVEL=INFO
```

### Storage Locations

By default, Depl0y stores data in:
- ISOs: `/var/lib/depl0y/isos`
- Cloud images: `/var/lib/depl0y/cloud-images`
- Cloud-init configs: `/var/lib/depl0y/cloud-init`
- SSH keys: `/var/lib/depl0y/ssh_keys`
- Logs: `/var/log/depl0y/`

These can be customized in the `.env` file.

## Architecture

Depl0y consists of three main components:

1. **Backend API** (FastAPI + Python)
   - RESTful API
   - Proxmox integration via proxmoxer
   - Database management with SQLAlchemy
   - Authentication and authorization
   - Runs as systemd service on port 8000

2. **Frontend** (Vue.js 3)
   - Single-page application
   - Responsive design
   - Real-time updates
   - Served by nginx as reverse proxy

3. **Database** (SQLite)
   - Stores users, VMs, hosts, and configuration
   - Lightweight and embedded
   - Automated backups recommended

## API Documentation

Once installed, API documentation is available at:
- Swagger UI: `http://your-server-ip/api/v1/docs`
- ReDoc: `http://your-server-ip/api/v1/redoc`

## Usage

### ⚡ Deploying with Cloud Images (Fastest - Recommended)

Cloud images provide **30-second deployments** after initial setup:

**One-Time Setup (1 minute):**
1. Go to **Settings** > **Cloud Image Setup**
2. Copy the setup command shown
3. SSH to your Depl0y server and run: `sudo /tmp/enable_cloud_images.sh`
4. Enter your Proxmox root password when prompted
5. Done! All cloud images are now enabled

**Creating VMs:**
1. Navigate to "Virtual Machines" > "Create VM"
2. Select your Proxmox host and node
3. Choose **"Cloud Image (Fast)"** installation method
4. Select a cloud image (Ubuntu 24.04, Debian 12, etc.)
5. Configure resources (CPU, RAM, disk)
6. Set network configuration (DHCP or static IP)
7. Enter credentials for the VM
8. Click "Deploy"

**First deployment:** ~5-10 minutes (creates template)
**All subsequent deployments:** ~30 seconds ⚡

The VM will be automatically created with:
- OS fully installed and configured
- Your credentials already set up
- Network configured
- SSH server enabled
- Ready to use immediately

📖 **Full guide:** [CLOUD_IMAGES_GUIDE.md](CLOUD_IMAGES_GUIDE.md)

### Deploying a Linux VM (Traditional ISO Method)

1. Navigate to "Virtual Machines" > "Create VM"
2. Select your Proxmox host and node
3. Choose an OS type (Ubuntu, Debian, etc.)
4. Configure resources (CPU, RAM, disk)
5. Set network configuration (DHCP or static IP)
6. Enter credentials for the VM
7. Click "Deploy"

The VM will be automatically created with:
- Cloud-init configuration
- QEMU guest agent installed
- SSH server enabled
- User account configured

### Deploying a Windows VM

1. First upload a Windows ISO to "ISO Images"
2. Create a new VM and select Windows OS type
3. Configure resources
4. Deploy and complete Windows installation manually via VNC

### Managing Updates

1. Select a VM from the list
2. Click "Check Updates" to see available updates
3. Click "Install Updates" to apply them
4. View update history in the VM details

### Managing Proxmox Hosts

1. Go to "Proxmox Hosts"
2. Add your Proxmox VE hosts with credentials
3. Poll hosts to refresh resource information
4. View nodes and their current utilization

## Development

### Backend Development

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm run test
```

### Deploying Changes

After making changes to the code, deploy them to production:

```bash
# Quick deploy with the deploy script
./deploy.sh

# Or deploy manually - see DEPLOYMENT.md for details
```

📖 **Full deployment guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Security

### Reporting Vulnerabilities

Please report security vulnerabilities to **agit8or@agit8or.net** with the subject line "Depl0y Security Vulnerability" (not via public issues).

See [SECURITY.md](SECURITY.md) for our complete security policy.

### Best Practices

- Change default passwords immediately after installation
- Use strong, unique passwords
- Enable 2FA for all admin accounts
- Keep Depl0y updated to the latest version
- Use HTTPS in production (configure SSL certificates)
- Regularly backup your database
- Restrict network access to trusted IPs if possible

## Roadmap

- [x] Cloud images for ultra-fast deployment
- [x] Template-based VM cloning
- [ ] Scheduled deployments
- [ ] VM snapshots management
- [ ] Backup automation
- [ ] Integration with monitoring tools (Prometheus, Grafana)
- [ ] Multi-language support
- [ ] Mobile app
- [ ] Ansible playbook execution
- [ ] Cost tracking and reporting
- [ ] API rate limiting

## Troubleshooting

### Common Issues

**Cannot connect to Proxmox host**
- Verify credentials are correct
- Check network connectivity
- Ensure Proxmox API is accessible
- Verify SSL certificate settings

**VMs not starting**
- Check Proxmox node has sufficient resources
- Verify ISO image is available
- Check VM logs in Proxmox

**Database connection errors**
- Verify database file exists at `/var/lib/depl0y/db/depl0y.db`
- Check file permissions (`depl0y` user needs read/write access)
- Review backend logs: `sudo journalctl -u depl0y-backend`

For more help, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) or open an issue.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Frontend powered by [Vue.js](https://vuejs.org/)
- Proxmox integration via [proxmoxer](https://github.com/proxmoxer/proxmoxer)
- Icons from various open-source projects

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/agit8or1/Depl0y/issues)
- **Discussions**: [GitHub Discussions](https://github.com/agit8or1/Depl0y/discussions)
- **Email**: agit8or@agit8or.net

## Author

Created with ❤️ by the Depl0y team and contributors.

---

**Star this repo if you find it useful!** ⭐

