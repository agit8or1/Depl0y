# Proxmox API Tokens for 2FA Authentication

When your Proxmox VE server has Two-Factor Authentication (2FA) enabled, you need to use **API Tokens** instead of password authentication for programmatic access.

## Why API Tokens?

- **Bypass 2FA**: API tokens don't require 2FA codes, making them perfect for automated systems
- **More Secure**: Can be revoked without changing your main password
- **Fine-grained Permissions**: Can be restricted to specific operations
- **Audit Trail**: API token usage is logged separately

## Creating an API Token in Proxmox

### Step 1: Log into Proxmox Web Interface

1. Navigate to your Proxmox web interface: `https://your-proxmox-host:8006`
2. Log in with your credentials (including 2FA if enabled)

### Step 2: Navigate to API Tokens

1. Click on **Datacenter** in the left sidebar
2. Expand **Permissions**
3. Click on **API Tokens**

### Step 3: Create a New Token

1. Click the **Add** button at the top
2. Fill in the token details:
   - **User**: Select the user (e.g., `root@pam`)
   - **Token ID**: Give it a meaningful name (e.g., `depl0y`)
   - **Privilege Separation**: **UNCHECK** this box (important!)
     - Unchecking this gives the token the same permissions as the user
     - Checking it would create a token with limited permissions
   - **Expiration**: Leave empty for no expiration, or set an expiration date

3. Click **Add**

### Step 4: Save the Token Secret

**IMPORTANT**: After clicking Add, you'll see a screen showing the **Token Secret**.

```
Token ID: root@pam!depl0y
Token Secret: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**Copy and save this secret immediately!** You won't be able to see it again.

## Using API Tokens in Depl0y

When adding a Proxmox host in Depl0y:

1. Go to **Proxmox Hosts** → **+ Add Host**
2. Fill in basic details:
   - Name: Any name for your reference
   - Hostname/IP: Your Proxmox server address
   - Port: 8006 (default)
   - Username: `root@pam` (the user who owns the token)

3. **Check** the box: "Use API Token (recommended for 2FA-enabled Proxmox)"

4. Enter token details:
   - **API Token ID**: You can use either format:
     - **Full format**: `root@pam!depl0y` (the complete Token ID from Proxmox)
     - **Short format**: `depl0y` (just the token name)
   - **API Token Secret**: The UUID-like secret you copied earlier

5. Optionally check "Verify SSL Certificate" if you have a valid SSL cert

6. Click **Add Host**

## Example

If Proxmox shows your token as:
```
Token ID: root@pam!mytoken
Token Secret: 12345678-1234-1234-1234-123456789abc
```

In Depl0y, you can enter **either**:

**Option 1 (Full format - Recommended):**
- Username: `root@pam` (can be anything, will be extracted from token)
- API Token ID: `root@pam!mytoken`
- API Token Secret: `12345678-1234-1234-1234-123456789abc`

**Option 2 (Short format):**
- Username: `root@pam`
- API Token ID: `mytoken`
- API Token Secret: `12345678-1234-1234-1234-123456789abc`

## Troubleshooting

### Connection Failed
- Make sure "Privilege Separation" was UNCHECKED when creating the token
- Confirm the token hasn't expired
- Check that the Proxmox host is reachable from your Depl0y server
- Verify the token secret is correct (it's case-sensitive)
- Try using the full token format: `root@pam!tokenname`

### Permission Denied
- Ensure "Privilege Separation" was unchecked when creating the token
- Verify the user account has sufficient permissions
- Check Proxmox logs: `/var/log/pve/tasks/`

### Token Not Working After Creation
- API tokens may need a few seconds to become active
- Try refreshing the Proxmox web interface
- Log out and back in to Proxmox

## Security Best Practices

1. **Use Separate Tokens**: Create different tokens for different applications
2. **Set Expiration**: Consider setting expiration dates for tokens
3. **Revoke Unused Tokens**: Regularly audit and remove tokens you no longer use
4. **Store Securely**: Keep token secrets secure, like passwords
5. **Monitor Usage**: Check Proxmox logs for API token usage

## Revoking a Token

To revoke an API token:

1. Go to **Datacenter** → **Permissions** → **API Tokens**
2. Select the token you want to revoke
3. Click **Remove**
4. Confirm the removal

The token will be immediately revoked and can no longer be used.
