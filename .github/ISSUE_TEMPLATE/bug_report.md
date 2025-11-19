---
name: Bug Report
about: Create a report to help us improve Depl0y
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description
A clear and concise description of what the bug is.

## Steps to Reproduce
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

## Expected Behavior
A clear and concise description of what you expected to happen.

## Actual Behavior
What actually happened instead.

## Screenshots
If applicable, add screenshots to help explain your problem.

## Environment
- **Depl0y Version**: [e.g., 1.2.0]
- **OS**: [e.g., Ubuntu 22.04]
- **Browser** (if UI issue): [e.g., Chrome 120]
- **Proxmox VE Version**: [e.g., 8.1]

## Logs
Please provide relevant log output:

```
# Backend logs
sudo journalctl -u depl0y-backend -n 50

# Or application logs
tail -50 /var/log/depl0y/app.log
```

## Additional Context
Add any other context about the problem here.
