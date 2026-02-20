# UTM Template VM Setup for Brainbox

This guide explains how to create a "golden image" macOS VM template in UTM that brainbox can clone for isolated iOS/macOS development environments.

## Overview

Brainbox's UTM backend clones a template VM for each session, providing:
- **Full macOS environment** for Xcode, iOS Simulator, Swift development
- **Isolated sessions** via VM cloning
- **SSH-only access** (no web terminal)
- **VirtioFS volume mounting** for sharing host directories with the VM

## Prerequisites

- **macOS host** (Intel or Apple Silicon)
- **UTM** 4.0+ ([download](https://mac.getutm.app/) or `brew install --cask utm`)
- **UTM command-line tools**: Install via `brew install utmctl` or from UTM preferences
- **macOS installer** (macOS 13 Ventura or later recommended for VirtioFS support)
- **SSH key pair**: Generate with `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519` if you don't have one

## Step 1: Create the Base VM

1. **Open UTM** and click "Create a New Virtual Machine"
2. **Select "Virtualize"** (not Emulate)
3. **Choose macOS** as the operating system
4. **Configure resources:**
   - **Memory**: 8 GB minimum, 16 GB recommended
   - **CPU cores**: 4 minimum, 8 recommended
   - **Disk size**: 100 GB minimum (VMs will be cloned, so this is per-session)
5. **Set VM name**: `brainbox-macos-template`
6. **Install macOS**: Follow the installer prompts to install macOS 13+ (Ventura or Sonoma recommended)

## Step 2: Initial macOS Setup

After macOS installation completes:

1. **Create user account**:
   - Username: `developer` (brainbox expects this username)
   - Password: Set a password (you'll use this for SSH and sudo)
2. **Complete macOS setup wizard**:
   - Skip iCloud sign-in (optional)
   - Disable analytics (recommended)
   - Skip Touch ID setup
3. **Update macOS**: Run Software Update to get the latest patches

## Step 3: Install Development Tools

Open Terminal in the VM and run:

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add Homebrew to PATH
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install Xcode Command Line Tools
xcode-select --install

# Install Claude Code CLI
brew install claudeai/claude-code/claude-code

# Optional: Install full Xcode from App Store if needed
```

## Step 4: Configure SSH Access

1. **Enable Remote Login**:
   - Open System Settings → General → Sharing
   - Enable "Remote Login"
   - Set "Allow full disk access for remote users"

2. **Add your public key** to the VM's `~/.ssh/authorized_keys`:
   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh

   # Copy your public key from the host (run this on your host Mac):
   cat ~/.ssh/id_ed25519.pub | pbcopy

   # Then in the VM, paste it:
   nano ~/.ssh/authorized_keys
   # Paste the key, save and exit (Ctrl+X, Y, Enter)

   chmod 600 ~/.ssh/authorized_keys
   ```

3. **Test SSH from host** (find VM IP with `ifconfig en0` in VM):
   ```bash
   ssh developer@<VM_IP>
   ```

   If this works, SSH is configured correctly.

4. **Configure passwordless sudo** (required for VirtioFS mounting):
   ```bash
   # Add developer user to sudoers with NOPASSWD
   echo 'developer ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/developer
   sudo chmod 440 /etc/sudoers.d/developer

   # Test passwordless sudo
   sudo -n true
   ```

   If the test succeeds with no password prompt, passwordless sudo is configured correctly.

## Step 5: Configure Network for Port Forwarding

UTM needs to be configured to forward SSH from guest to host:

1. **Shut down the VM** (important: must be stopped to edit config)
2. In UTM, **right-click the VM** → "Edit"
3. Go to **Network** tab
4. Change mode to **"Emulated VLAN"** (required for port forwarding)
5. Click **Save**

**Note**: Port forwarding will be configured automatically by brainbox when it clones the VM. The default is guest port 22 → host port 2200 (increments for multiple VMs).

## Step 6: Configure Claude Code (Optional)

Pre-configure Claude Code to skip onboarding:

```bash
# Create config directory
mkdir -p ~/.claude

# Optional: Set up API key if not using 1Password
echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zprofile
```

Brainbox will automatically:
- Inject API keys via SSH
- Set `hasCompletedOnboarding: true`
- Configure bypass permissions mode

## Step 7: Configure Shared Directories (Optional)

To share files between the host and VM:

1. **Stop the template VM** (must be stopped to edit settings)
2. **In UTM**, right-click the VM → "Edit"
3. Go to **Sharing** tab
4. Click **"+"** to add a shared directory
5. Select the directory you want to share (e.g., your project directory)
6. Click **Save**

**How it works:**
- Shared directories automatically appear at `/Volumes/My Shared Files/<folder-name>` inside the VM
- No manual mounting required - they're available immediately after VM boot
- You can access them directly or create symlinks to convenient locations

**Example:**
```bash
# Inside the VM, after sharing ~/projects from host:
ls "/Volumes/My Shared Files/projects"

# Create a convenient symlink:
ln -s "/Volumes/My Shared Files/projects" ~/workspace
```

**Note:** Currently, shared directories must be configured manually through UTM's GUI. Programmatic configuration via the API is not yet supported for Apple VMs.

## Step 8: Optimize VM for Cloning

Before shutting down the template:

```bash
# Clear shell history
history -c
rm ~/.zsh_history

# Clear temporary files
sudo rm -rf /tmp/*
sudo rm -rf ~/Library/Caches/*

# Clear logs
sudo rm -rf /var/log/*
```

## Step 9: Final Shutdown

1. **Shut down the VM cleanly**: Apple menu → Shut Down
2. **Verify VM is stopped** in UTM
3. **Do not start the template again** — brainbox will clone it

The template is now ready!

## Step 9: Configure Brainbox

Set the template name in your environment (if not using default):

```bash
export CL_UTM__DEFAULT_TEMPLATE=brainbox-macos-template
```

Other optional settings:

```bash
# SSH port range (default: 2200+)
export CL_UTM__SSH_BASE_PORT=2200

# Custom SSH key (default: ~/.ssh/id_ed25519)
export CL_UTM__SSH_KEY_PATH=~/.ssh/id_rsa

# Custom UTM documents directory (default: auto-detected)
export CL_UTM__DOCS_DIR=~/Library/Containers/com.utmapp.UTM/Data/Documents

# Custom utmctl path (default: /usr/local/bin/utmctl)
export CL_UTM__UTMCTL_PATH=/opt/homebrew/bin/utmctl
```

## Usage

Create a UTM session via API:

```bash
curl -X POST http://localhost:9999/api/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ios-project",
    "backend": "utm",
    "vm_template": "brainbox-macos-template",
    "volumes": ["/Users/you/ios-project:/home/developer/workspace:rw"]
  }'
```

Or via the dashboard:
1. Click "**+ new session**"
2. Select backend: **"UTM macOS VM"**
3. Enter session name and volume mounts
4. Click **Create**

Connect via SSH:

```bash
# SSH port is returned in the API response or shown in dashboard
ssh -p 2200 developer@localhost
```

## Troubleshooting

### SSH Connection Refused

**Symptom**: `Connection refused` when trying to SSH

**Solutions**:
1. Check VM is running: `utmctl status brainbox-<session-name>`
2. Verify port forwarding: Check `config.plist` in the cloned VM's `.utm` package
3. Test SSH inside VM first: Boot the template VM and verify `System Settings → Sharing → Remote Login` is enabled

### VirtioFS Mount Fails

**Symptom**: Shared directories not visible in VM

**Solutions**:
1. Requires **macOS 13+** guest (Ventura or later)
2. Check mount command: `sudo mount_virtiofs <share_tag> /Volumes/<mount_point>`
3. Verify share tag in `config.plist` under `SharedDirectories`

### VM Clone Slow

**Symptom**: Provisioning takes 60+ seconds

**Expected**: VM cloning is slower than Docker container creation. UTM must copy the entire `.utm` package (50-100 GB).

**Optimization**:
- Store VMs on fast SSD
- Use sparse disk images (UTM default)
- Reduce VM disk size if possible

### utmctl Not Found

**Symptom**: `utmctl: command not found`

**Solution**: Install via Homebrew: `brew install utmctl` or set `CL_UTM__UTMCTL_PATH`

### "Template not found" Error

**Symptom**: Brainbox can't find template VM

**Solution**: Verify template name matches exactly (case-sensitive):
```bash
ls ~/Library/Containers/com.utmapp.UTM/Data/Documents/
# Should show: brainbox-macos-template.utm
```

## Maintenance

### Updating the Template

To update Xcode, Homebrew, or other tools:

1. **Clone the template manually** in UTM (right-click → Clone)
2. **Boot the clone** (not the original template)
3. **Update software**:
   ```bash
   brew update && brew upgrade
   softwareupdate --install --recommended
   ```
4. **Clean up** (see Step 7 above)
5. **Shut down** the clone
6. **Rename clone** to `brainbox-macos-template` (delete old template first)

### Disk Space Management

Each cloned VM is 50-100 GB. Monitor usage:

```bash
# List all brainbox VMs
ls ~/Library/Containers/com.utmapp.UTM/Data/Documents/brainbox-*.utm

# Calculate total disk usage
du -sh ~/Library/Containers/com.utmapp.UTM/Data/Documents/brainbox-*.utm
```

Brainbox automatically deletes VMs on recycle, but orphaned VMs may accumulate if crashes occur. Manually clean up:

```bash
# List stopped VMs
utmctl list

# Delete specific VM
rm -rf ~/Library/Containers/com.utmapp.UTM/Data/Documents/brainbox-<name>.utm
```

## Security Considerations

### VM Isolation

- **VMs are NOT sandboxed** like Docker containers
- Each VM has full macOS capabilities (network, filesystem, etc.)
- Use separate user accounts or FileVault encryption if handling sensitive data

### SSH Keys

- Brainbox uses **passwordless SSH** with key-based authentication
- Protect your private key: `chmod 600 ~/.ssh/id_ed25519`
- Consider using separate keys for brainbox VMs vs. production systems

### Network Access

- VMs use NAT networking (isolated from host network by default)
- Port forwarding exposes SSH on localhost only
- No direct incoming connections from external networks

## Limitations

See CLAUDE.md "Known Limitations" section for full details:

- **Slow provisioning**: 30-60s vs 1-2s for Docker
- **No labels/metadata**: Cannot filter VMs like Docker containers
- **SSH-only access**: No web terminal integration
- **Large disk footprint**: 50-100 GB per VM
- **macOS 13+ for VirtioFS**: Older guests cannot mount shared folders

## References

- [UTM Documentation](https://docs.getutm.app/)
- [UTM macOS Guest Setup](https://docs.getutm.app/guest-support/macos/)
- [VirtioFS Mounting](https://docs.getutm.app/guest-support/macos/#shared-directories)
- [utmctl CLI Reference](https://docs.getutm.app/advanced/scripting/)
