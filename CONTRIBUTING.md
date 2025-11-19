# Contributing to Depl0y

Thank you for your interest in contributing to Depl0y! We welcome contributions from the community.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check the existing issues to avoid duplicates.

When filing a bug report, include:

- **Clear title**: Describe the issue concisely
- **Steps to reproduce**: Detailed steps to recreate the problem
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Environment**: 
  - Depl0y version
  - Operating system
  - Proxmox VE version
  - Browser (if UI-related)
- **Screenshots**: If applicable
- **Logs**: Relevant log output from `/var/log/depl0y/` or systemd journal

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear title** that describes the enhancement
- **Provide detailed description** of the proposed functionality
- **Explain why this enhancement would be useful** to most users
- **List alternatives you've considered**
- **Include mockups or examples** if applicable

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** with clear, logical commits
3. **Test your changes** thoroughly
4. **Update documentation** if needed
5. **Follow the code style** guidelines below
6. **Write good commit messages** (see below)
7. **Submit a pull request**

#### Pull Request Process

1. Update the README.md or documentation with details of changes if applicable
2. Update the CHANGELOG.md following the existing format
3. The PR will be merged once you have the sign-off of a maintainer

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- SQLite 3
- Git

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/agit8or1/Depl0y.git
   cd Depl0y
   ```

2. **Backend setup**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Frontend setup**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Database setup**:
   ```bash
   # The installer script handles this in production
   # For development, you can manually initialize the database
   sqlite3 /var/lib/depl0y/db/depl0y.db < backend/schema.sql
   ```

5. **Run backend**:
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Run frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

### Testing

Before submitting a PR, ensure:

1. **Backend tests pass**:
   ```bash
   cd backend
   pytest
   ```

2. **Frontend builds successfully**:
   ```bash
   cd frontend
   npm run build
   ```

3. **Manual testing**:
   - Test the specific feature you added/modified
   - Test related features that might be affected
   - Test in both fresh install and upgrade scenarios

## Code Style Guidelines

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints where appropriate
- Write docstrings for functions and classes
- Keep functions focused and single-purpose
- Maximum line length: 100 characters

Example:
```python
def create_vm(vm_config: VMConfig) -> VM:
    """
    Create a new VM in Proxmox.
    
    Args:
        vm_config: Configuration for the new VM
        
    Returns:
        The created VM object
        
    Raises:
        ProxmoxException: If VM creation fails
    """
    # Implementation
```

### JavaScript/Vue (Frontend)

- Use ES6+ syntax
- Follow Vue.js style guide
- Use composition API for new components
- Keep components small and focused
- Use descriptive variable names

Example:
```javascript
const deployVM = async (vmConfig) => {
  try {
    const response = await api.post('/vms', vmConfig)
    return response.data
  } catch (error) {
    console.error('Failed to deploy VM:', error)
    throw error
  }
}
```

### Bash (Scripts)

- Use `#!/bin/bash` shebang
- Add error checking with `set -e` where appropriate
- Use meaningful variable names in UPPER_CASE
- Add comments for complex logic
- Quote variables to prevent word splitting

## Commit Message Format

Use clear, descriptive commit messages:

```
<type>: <subject>

<body>

<footer>
```

### Types:
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, no logic change)
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

### Examples:

```
feat: add cloud image template creation

Implement automated cloud image template creation with cloud-init
support. Includes inter-node SSH setup for clustered environments.

Closes #123
```

```
fix: correct VM state polling interval

Changed polling from 30s to 60s to reduce API load on Proxmox hosts.

Fixes #456
```

## Project Structure

```
Depl0y/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/         # API endpoints
│   │   ├── core/        # Core functionality
│   │   ├── models/      # Database models
│   │   ├── schemas/     # Pydantic schemas
│   │   └── services/    # Business logic
│   ├── requirements.txt
│   └── main.py
├── frontend/            # Vue.js frontend
│   ├── src/
│   │   ├── components/  # Vue components
│   │   ├── views/       # Page views
│   │   ├── stores/      # Pinia stores
│   │   └── router/      # Vue Router
│   ├── package.json
│   └── vite.config.js
├── install.sh           # Installation script
├── deploy.sh           # Deployment script
└── README.md
```

## Questions?

If you have questions about contributing, feel free to:

- Open an issue with the "question" label
- Email: agit8or@agit8or.net

## License

By contributing to Depl0y, you agree that your contributions will be licensed under the MIT License.
