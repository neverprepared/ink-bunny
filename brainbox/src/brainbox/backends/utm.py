"""UTM backend implementation for brainbox.

Manages macOS VMs via UTM for iOS/macOS development workflows requiring Xcode,
Swift, and native macOS tooling.
"""

from __future__ import annotations

import asyncio
import json
import os
import plistlib
import shlex
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

from ..log import get_logger
from ..models import SessionContext, SessionState

log = get_logger()

# Default paths (configurable via environment)
DEFAULT_UTM_DOCS = Path.home() / "Library" / "Containers" / "com.utmapp.UTM" / "Data" / "Documents"
DEFAULT_UTMCTL = "/usr/local/bin/utmctl"
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "id_ed25519"
DEFAULT_SSH_BASE_PORT = 2200


def _get_utmctl_path() -> str:
    """Get utmctl binary path from env or default."""
    return os.environ.get("CL_UTM__UTMCTL_PATH", str(DEFAULT_UTMCTL))


def _get_utm_docs_dir() -> Path:
    """Get UTM documents directory path."""
    custom = os.environ.get("CL_UTM__DOCS_DIR")
    if custom:
        return Path(custom)
    return DEFAULT_UTM_DOCS


def _get_ssh_key_path() -> Path:
    """Get SSH private key path from env or default."""
    custom = os.environ.get("CL_UTM__SSH_KEY_PATH")
    if custom:
        return Path(custom)
    return DEFAULT_SSH_KEY


def _get_ssh_base_port() -> int:
    """Get SSH base port for allocation."""
    return int(os.environ.get("CL_UTM__SSH_BASE_PORT", str(DEFAULT_SSH_BASE_PORT)))


async def _run_subprocess(
    cmd: list[str], *, timeout: int = 30, check: bool = True
) -> tuple[int, str, str]:
    """Run subprocess asynchronously.

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        returncode = proc.returncode or 0

        if check and returncode != 0:
            raise subprocess.CalledProcessError(returncode, cmd, stdout, stderr)

        return (returncode, stdout, stderr)
    except asyncio.TimeoutError:
        proc.kill()
        raise TimeoutError(f"Command timed out after {timeout}s: {' '.join(cmd)}")


async def _discover_vm_ip(mac_address: str, timeout: int = 60) -> str:
    """Discover VM IP address via ARP table using MAC address.

    Args:
        mac_address: VM's MAC address (e.g., "a6:45:33:e5:e4:0d")
        timeout: How long to wait for VM to appear in ARP table

    Returns:
        VM's IP address

    Raises:
        TimeoutError: If VM IP not found within timeout
    """
    # Normalize MAC address for flexible matching (handles missing leading zeros)
    # ARP may show "a6:45:33:e5:e4:d" while config has "a6:45:33:e5:e4:0d"
    mac_parts = mac_address.lower().split(":")
    mac_pattern = ":".join(part.lstrip("0") or "0" for part in mac_parts)

    start_time = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start_time) < timeout:
        # Query ARP table
        returncode, stdout, stderr = await _run_subprocess(["arp", "-a"], timeout=5)
        if returncode == 0:
            # Parse ARP output: "? (192.168.64.12) at a6:45:33:e5:e4:d on bridge100"
            for line in stdout.split("\n"):
                line_lower = line.lower()
                # Check if MAC matches (with or without leading zeros)
                if mac_pattern in line_lower or mac_address.lower() in line_lower:
                    # Extract IP address
                    import re

                    match = re.search(r"\(([0-9.]+)\)", line)
                    if match:
                        return match.group(1)

        await asyncio.sleep(2)

    raise TimeoutError(f"VM IP not found in ARP table after {timeout}s (MAC: {mac_address})")


async def _ssh_execute(
    host: str,
    port: int,
    user: str,
    ssh_key: Path,
    command: str,
    *,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Execute command via SSH.

    Args:
        host: SSH hostname or IP address
        port: SSH port (22 for bridged, custom for port forwarding)
        user: SSH username
        ssh_key: Path to SSH private key
        command: Shell command to execute
        timeout: Command timeout in seconds

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    ssh_cmd = [
        "ssh",
        "-i",
        str(ssh_key),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "LogLevel=ERROR",
        "-p",
        str(port),
        f"{user}@{host}",
        command,
    ]
    return await _run_subprocess(ssh_cmd, timeout=timeout, check=False)


async def _wait_for_ssh(host: str, port: int, timeout: int = 120, interval: int = 2) -> bool:
    """Wait for SSH port to become available.

    Args:
        host: SSH hostname
        port: SSH port
        timeout: Maximum wait time in seconds
        interval: Polling interval in seconds

    Returns:
        True if SSH is available, False if timeout
    """
    elapsed = 0
    while elapsed < timeout:
        try:
            # Try to connect to SSH port
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            await asyncio.sleep(interval)
            elapsed += interval
    return False


def _find_available_ssh_port(start_port: int = None) -> int:
    """Find an available SSH port by scanning existing Docker and UTM usage.

    Args:
        start_port: Starting port number (defaults to CL_UTM__SSH_BASE_PORT)

    Returns:
        Available port number
    """
    if start_port is None:
        start_port = _get_ssh_base_port()

    used_ports: set[int] = set()

    # Scan Docker containers for used ports
    try:
        import docker

        client = docker.from_env()
        containers = client.containers.list()
        for c in containers:
            ports = c.attrs.get("NetworkSettings", {}).get("Ports") or {}
            for bindings in ports.values():
                if bindings:
                    for b in bindings:
                        if b.get("HostPort"):
                            used_ports.add(int(b["HostPort"]))
    except Exception:
        pass  # Docker not available or other error - continue

    # Scan existing UTM VMs for used SSH ports (read from config.plist)
    try:
        utm_docs = _get_utm_docs_dir()
        if utm_docs.exists():
            for vm_dir in utm_docs.glob("brainbox-*.utm"):
                config_plist = vm_dir / "config.plist"
                if config_plist.exists():
                    with config_plist.open("rb") as f:
                        config = plistlib.load(f)
                    # Check for port forwarding rules
                    qemu = config.get("Qemu", {})
                    network = qemu.get("Network", {})
                    port_forward = network.get("PortForward", [])
                    for rule in port_forward:
                        if isinstance(rule, dict):
                            host_port = rule.get("HostPort")
                            if host_port:
                                used_ports.add(int(host_port))
    except Exception:
        pass  # Ignore errors reading configs

    # Find first available port
    port = start_port
    while port in used_ports:
        port += 1
    return port


class UTMBackend:
    """UTM VM backend for brainbox."""

    async def provision(
        self,
        ctx: SessionContext,
        *,
        image_or_template: str,
        volumes: dict[str, dict[str, str]],
        hardening_kwargs: dict[str, Any],
    ) -> SessionContext:
        """Clone UTM VM template and configure shared directories.

        Args:
            ctx: Session context with vm_template field set
            image_or_template: UTM template name (e.g., "brainbox-macos-template")
            volumes: Volume mounts in Docker format {host_path: {"bind": container_path, "mode": "rw"}}
            hardening_kwargs: Ignored for UTM (no container hardening)

        Returns:
            Updated SessionContext with vm_path and ssh_port
        """
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        utm_docs = _get_utm_docs_dir()

        # Validate utmctl exists
        utmctl = _get_utmctl_path()
        if not Path(utmctl).exists():
            raise FileNotFoundError(
                f"utmctl not found at {utmctl}. "
                "Install UTM command-line tools or set CL_UTM__UTMCTL_PATH"
            )

        # Validate template exists
        template_path = utm_docs / f"{image_or_template}.utm"
        if not template_path.exists():
            raise FileNotFoundError(
                f"UTM template not found: {template_path}. "
                f"Create a golden image VM named '{image_or_template}' in UTM. "
                "See brainbox/docs/utm-setup.md for setup instructions."
            )

        # Clone VM
        vm_name = f"brainbox-{ctx.session_name}"
        vm_path = utm_docs / f"{vm_name}.utm"

        # Remove existing VM if present
        if vm_path.exists():
            slog.info("utm.removing_existing_vm", metadata={"path": str(vm_path)})
            try:
                # Stop VM first
                await _run_subprocess([utmctl, "stop", vm_name], check=False)
                await asyncio.sleep(2)
                shutil.rmtree(vm_path)
            except Exception as exc:
                slog.warning("utm.remove_failed", metadata={"reason": str(exc)})

        # Clone template (preserve symlinks)
        slog.info("utm.cloning_template", metadata={"template": image_or_template})
        try:
            shutil.copytree(template_path, vm_path, symlinks=True)
        except Exception as exc:
            slog.error("utm.clone_failed", metadata={"reason": str(exc)})
            raise

        # Allocate SSH port
        ssh_port = _find_available_ssh_port()

        # Edit config.plist
        config_plist = vm_path / "config.plist"
        if not config_plist.exists():
            raise FileNotFoundError(f"config.plist not found in cloned VM: {config_plist}")

        try:
            with config_plist.open("rb") as f:
                config = plistlib.load(f)

            # Update VM name
            config["Name"] = vm_name
            if "Information" not in config:
                config["Information"] = {}
            config["Information"]["Name"] = vm_name

            # Configure SSH port forwarding (guest 22 → host ssh_port)
            # Check backend type (Apple or QEMU)
            backend_type = config.get("Backend", "QEMU")

            if backend_type == "Apple":
                # Apple Virtualization Framework with Bridged networking
                # Network is a list of interfaces for Apple VMs
                network_list = config.setdefault("Network", [])
                if not network_list:
                    network_list.append({"Mode": "Bridged"})

                # Ensure first interface has bridged mode and extract MAC address
                if len(network_list) > 0:
                    network_list[0]["Mode"] = "Bridged"
                    mac_address = network_list[0].get("MacAddress")
                    if mac_address:
                        ctx.mac_address = mac_address
                    # Remove port forwarding (not used with bridged)
                    network_list[0].pop("PortForward", None)
                else:
                    raise ValueError("No network interfaces found in Apple VM config")
            else:
                # QEMU with port forwarding (Network is a dict)
                qemu = config.setdefault("Qemu", {})
                network = qemu.setdefault("Network", {})
                network["Mode"] = "Shared"
                port_forward = network.setdefault("PortForward", [])

                # Remove existing SSH forwarding rules
                port_forward[:] = [
                    rule
                    for rule in port_forward
                    if isinstance(rule, dict) and rule.get("GuestPort") != 22
                ]

                # Add new SSH forwarding rule
                port_forward.append(
                    {
                        "Protocol": "tcp",
                        "GuestAddress": "0.0.0.0",
                        "GuestPort": 22,
                        "HostAddress": "127.0.0.1",
                        "HostPort": ssh_port,
                    }
                )

            # Add VirtioFS shared directories for volume mounts
            shared_dirs = config.setdefault("SharedDirectories", [])
            # Clear existing shares
            shared_dirs.clear()

            for host_path, mount_spec in volumes.items():
                container_path = mount_spec["bind"]
                mode = mount_spec.get("mode", "rw")
                read_only = mode == "ro"

                # Generate share tag (used for mount_virtiofs)
                share_tag = f"share-{len(shared_dirs)}"

                shared_dirs.append(
                    {
                        "DirectoryURL": f"file://{host_path}",
                        "ReadOnly": read_only,
                        "Name": share_tag,
                    }
                )

                # Store mapping for configure phase
                if not hasattr(ctx, "_virtiofs_mounts"):
                    ctx._virtiofs_mounts = []  # type: ignore
                ctx._virtiofs_mounts.append((share_tag, container_path))  # type: ignore

            # Write updated config
            with config_plist.open("wb") as f:
                plistlib.dump(config, f)

            # Register VM with UTM by opening it
            subprocess.run(["open", vm_path], capture_output=True)
            await asyncio.sleep(2)  # Give UTM time to register the VM

        except Exception as exc:
            slog.error("utm.config_update_failed", metadata={"reason": str(exc)})
            raise

        # Update context
        ctx.vm_path = str(vm_path)
        ctx.ssh_port = ssh_port
        ctx.state = SessionState.CONFIGURING

        slog.info(
            "utm.provisioned",
            metadata={
                "template": image_or_template,
                "vm_name": vm_name,
                "ssh_port": ssh_port,
                "shared_dirs": len(volumes),
            },
        )
        return ctx

    async def configure(
        self,
        ctx: SessionContext,
        *,
        secrets: dict[str, str],
        env_content: str | None = None,
        oauth_account: dict[str, Any] | None = None,
        profile_env: str | None = None,
    ) -> SessionContext:
        """SSH into VM and inject secrets/configuration.

        Args:
            ctx: Session context with vm_path and ssh_port
            secrets: Secret key-value pairs to inject
            env_content: Ignored for UTM (uses secrets dict directly)
            oauth_account: Claude Code OAuth account data
            profile_env: Workspace profile environment variables

        Returns:
            Updated SessionContext
        """
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        utmctl = _get_utmctl_path()
        vm_name = f"brainbox-{ctx.session_name}"
        ssh_key = _get_ssh_key_path()

        if not ssh_key.exists():
            raise FileNotFoundError(
                f"SSH key not found: {ssh_key}. "
                "Generate a key pair and add the public key to the template VM's ~/.ssh/authorized_keys"
            )

        # Boot VM temporarily
        slog.info("utm.booting_for_config")
        await _run_subprocess([utmctl, "start", vm_name], timeout=60)

        # Determine SSH connection parameters
        if ctx.mac_address:
            # Bridged networking - discover IP
            slog.info("utm.discovering_ip_for_config", metadata={"mac": ctx.mac_address})
            vm_ip = await _discover_vm_ip(ctx.mac_address, timeout=60)
            ctx.vm_ip = vm_ip
            ssh_host = vm_ip
            ssh_port = 22
            slog.info("utm.ip_discovered", metadata={"ip": vm_ip})
        else:
            # Port forwarding
            ssh_host = "localhost"
            ssh_port = ctx.ssh_port

        # Wait for SSH
        slog.info("utm.waiting_for_ssh", metadata={"host": ssh_host, "port": ssh_port})
        ssh_ready = await _wait_for_ssh(ssh_host, ssh_port, timeout=120)
        if not ssh_ready:
            slog.error("utm.ssh_timeout")
            raise TimeoutError(f"SSH not available at {ssh_host}:{ssh_port} after 120s")

        # Inject secrets to ~/.env
        try:
            # Create/clear .env
            await _ssh_execute(
                ssh_host,
                ssh_port,
                ctx.ssh_user,
                ssh_key,
                "rm -f ~/.env && touch ~/.env && chmod 600 ~/.env",
            )

            # Write each secret
            for key, value in secrets.items():
                if key == "agent-token":
                    # Write agent-token to separate file
                    escaped_value = shlex.quote(value)
                    await _ssh_execute(
                        "localhost",
                        ctx.ssh_port,
                        ctx.ssh_user,
                        ssh_key,
                        f"echo {escaped_value} > ~/.agent-token && chmod 400 ~/.agent-token",
                    )
                else:
                    # Write to .env
                    escaped_value = shlex.quote(value)
                    await _ssh_execute(
                        "localhost",
                        ctx.ssh_port,
                        ctx.ssh_user,
                        ssh_key,
                        f"echo 'export {key}={escaped_value}' >> ~/.env",
                    )

            slog.info("utm.secrets_injected", metadata={"count": len(secrets)})

        except Exception as exc:
            slog.error("utm.secret_injection_failed", metadata={"reason": str(exc)})
            raise

        # Patch Claude config
        if oauth_account:
            try:
                claude_json_patch = {
                    "hasCompletedOnboarding": True,
                    "bypassPermissionsModeAccepted": True,
                    "oauthAccount": oauth_account,
                }
                patch_json = json.dumps(claude_json_patch)
                escaped_patch = shlex.quote(patch_json)

                await _ssh_execute(
                    "localhost",
                    ctx.ssh_port,
                    ctx.ssh_user,
                    ssh_key,
                    f"echo {escaped_patch} | python3 -c '"
                    "import json, pathlib, sys; "
                    "p = pathlib.Path.home() / '.claude.json'; "
                    "d = json.loads(p.read_text()) if p.exists() else {{}}; "
                    "d.update(json.load(sys.stdin)); "
                    "p.write_text(json.dumps(d, indent=2))"
                    "'",
                )
                slog.info("utm.claude_config_patched")
            except Exception as exc:
                slog.warning("utm.claude_config_patch_failed", metadata={"reason": str(exc)})

        # Mount VirtioFS shared directories
        if hasattr(ctx, "_virtiofs_mounts"):
            for share_tag, mount_point in ctx._virtiofs_mounts:  # type: ignore
                try:
                    # Create mount point
                    await _ssh_execute(
                        "localhost",
                        ctx.ssh_port,
                        ctx.ssh_user,
                        ssh_key,
                        f"sudo mkdir -p {mount_point}",
                    )

                    # Mount VirtioFS
                    await _ssh_execute(
                        "localhost",
                        ctx.ssh_port,
                        ctx.ssh_user,
                        ssh_key,
                        f"sudo mount_virtiofs {share_tag} {mount_point}",
                    )

                    slog.info(
                        "utm.virtiofs_mounted",
                        metadata={"share": share_tag, "mount_point": mount_point},
                    )
                except Exception as exc:
                    slog.warning(
                        "utm.virtiofs_mount_failed",
                        metadata={
                            "share": share_tag,
                            "mount_point": mount_point,
                            "reason": str(exc),
                        },
                    )

        # Shutdown VM
        slog.info("utm.shutting_down_after_config")
        await _run_subprocess([utmctl, "stop", vm_name], timeout=60)

        ctx.state = SessionState.STARTING
        slog.info("utm.configured")
        return ctx

    async def start(self, ctx: SessionContext) -> SessionContext:
        """Boot UTM VM and wait for SSH availability.

        Args:
            ctx: Session context

        Returns:
            Updated SessionContext with RUNNING state
        """
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        utmctl = _get_utmctl_path()
        vm_name = f"brainbox-{ctx.session_name}"

        # Boot VM
        slog.info("utm.starting_vm")
        await _run_subprocess([utmctl, "start", vm_name], timeout=60)

        # For bridged networking (Apple VMs), discover IP via ARP
        if ctx.mac_address:
            slog.info("utm.discovering_ip", metadata={"mac": ctx.mac_address})
            try:
                vm_ip = await _discover_vm_ip(ctx.mac_address, timeout=60)
                ctx.vm_ip = vm_ip
                slog.info("utm.ip_discovered", metadata={"ip": vm_ip})

                # Wait for SSH on discovered IP
                ssh_ready = await _wait_for_ssh(vm_ip, 22, timeout=120)
                if not ssh_ready:
                    slog.error("utm.ssh_timeout_after_start")
                    raise TimeoutError(f"SSH not available at {vm_ip}:22 after 120s")

                ctx.state = SessionState.RUNNING
                slog.info("utm.started", metadata={"ip": vm_ip})
            except TimeoutError as exc:
                slog.error("utm.ip_discovery_failed", metadata={"reason": str(exc)})
                raise
        else:
            # Port forwarding (QEMU VMs)
            slog.info("utm.waiting_for_ssh", metadata={"port": ctx.ssh_port})
            ssh_ready = await _wait_for_ssh("localhost", ctx.ssh_port, timeout=120)
            if not ssh_ready:
                slog.error("utm.ssh_timeout_after_start")
                raise TimeoutError(f"SSH not available on port {ctx.ssh_port} after 120s")

            ctx.state = SessionState.RUNNING
            slog.info("utm.started", metadata={"ssh_port": ctx.ssh_port})

        return ctx

    async def stop(self, ctx: SessionContext) -> SessionContext:
        """Shut down UTM VM.

        Args:
            ctx: Session context

        Returns:
            Updated SessionContext
        """
        utmctl = _get_utmctl_path()
        vm_name = f"brainbox-{ctx.session_name}"

        try:
            await _run_subprocess([utmctl, "stop", vm_name], timeout=60)
        except Exception:
            pass  # Ignore errors (VM might already be stopped)

        return ctx

    async def remove(self, ctx: SessionContext) -> SessionContext:
        """Stop UTM VM and delete .utm package.

        Args:
            ctx: Session context with vm_path

        Returns:
            Updated SessionContext
        """
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        utmctl = _get_utmctl_path()
        vm_name = f"brainbox-{ctx.session_name}"

        # Stop VM first
        try:
            await _run_subprocess([utmctl, "stop", vm_name], timeout=60, check=False)
            await asyncio.sleep(2)  # Give VM time to fully stop
        except Exception:
            pass

        # Delete .utm package
        if ctx.vm_path:
            vm_path = Path(ctx.vm_path)
            if vm_path.exists():
                try:
                    shutil.rmtree(vm_path)
                    slog.info("utm.removed", metadata={"path": str(vm_path)})
                except Exception as exc:
                    slog.error("utm.remove_failed", metadata={"reason": str(exc)})
                    raise

        return ctx

    async def health_check(self, ctx: SessionContext) -> dict[str, Any]:
        """Check UTM VM state and SSH connectivity.

        Args:
            ctx: Session context

        Returns:
            Health metrics dict with SSH status
        """
        utmctl = _get_utmctl_path()
        vm_name = f"brainbox-{ctx.session_name}"

        try:
            # Check VM status
            returncode, stdout, stderr = await _run_subprocess(
                [utmctl, "status", vm_name], timeout=10, check=False
            )

            if returncode != 0:
                return {
                    "backend": "utm",
                    "healthy": False,
                    "reason": f"utmctl status failed: {stderr}",
                }

            vm_state = stdout.strip().lower()

            if vm_state != "running":
                return {
                    "backend": "utm",
                    "healthy": False,
                    "reason": f"VM not running (state: {vm_state})",
                }

            # Check SSH connectivity
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(("localhost", ctx.ssh_port))
                sock.close()

                ssh_reachable = result == 0
            except Exception:
                ssh_reachable = False

            return {
                "backend": "utm",
                "healthy": ssh_reachable,
                "vm_state": vm_state,
                "ssh_port": ctx.ssh_port,
                "ssh_reachable": ssh_reachable,
            }

        except Exception as exc:
            return {
                "backend": "utm",
                "healthy": False,
                "reason": str(exc),
            }

    async def exec_command(
        self, ctx: SessionContext, command: list[str], **kwargs: Any
    ) -> tuple[int, bytes]:
        """Execute command in UTM VM via SSH.

        Args:
            ctx: Session context
            command: Command and arguments to execute
            **kwargs: Ignored for UTM (SSH doesn't support Docker exec kwargs)

        Returns:
            Tuple of (exit_code, output)
        """
        ssh_key = _get_ssh_key_path()

        # Convert command list to shell command string
        shell_cmd = " ".join(shlex.quote(arg) for arg in command)

        returncode, stdout, stderr = await _ssh_execute(
            "localhost",
            ctx.ssh_port,
            ctx.ssh_user,
            ssh_key,
            shell_cmd,
            timeout=kwargs.get("timeout", 30),
        )

        # Combine stdout and stderr (like Docker exec does)
        output = (stdout + stderr).encode("utf-8")

        return (returncode, output)

    def get_sessions_info(self) -> list[dict[str, Any]]:
        """List all managed UTM VMs (brainbox- prefix).

        Returns:
            List of session info dicts
        """
        sessions = []
        try:
            utm_docs = _get_utm_docs_dir()
            if not utm_docs.exists():
                return sessions

            utmctl = _get_utmctl_path()
            if not Path(utmctl).exists():
                return sessions

            # Find all brainbox VMs
            for vm_dir in utm_docs.glob("brainbox-*.utm"):
                vm_name = vm_dir.stem  # Remove .utm extension
                session_name = vm_name.replace("brainbox-", "")

                # Get VM state via utmctl
                try:
                    result = subprocess.run(
                        [utmctl, "status", vm_name],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    vm_state = (
                        result.stdout.strip().lower() if result.returncode == 0 else "unknown"
                    )
                    is_running = vm_state == "running"
                except Exception:
                    vm_state = "unknown"
                    is_running = False

                # Read config for SSH port
                ssh_port = None
                try:
                    config_plist = vm_dir / "config.plist"
                    if config_plist.exists():
                        with config_plist.open("rb") as f:
                            config = plistlib.load(f)
                        qemu = config.get("Qemu", {})
                        network = qemu.get("Network", {})
                        port_forward = network.get("PortForward", [])
                        for rule in port_forward:
                            if isinstance(rule, dict) and rule.get("GuestPort") == 22:
                                ssh_port = rule.get("HostPort")
                                break
                except Exception:
                    pass

                sessions.append(
                    {
                        "backend": "utm",
                        "name": vm_name,
                        "session_name": session_name,
                        "port": ssh_port,
                        "url": None,  # No web terminal for UTM
                        "volume": "-",  # VirtioFS mounts not easily listed
                        "active": is_running,
                        "vm_state": vm_state,
                        "ssh_port": ssh_port,
                    }
                )

        except Exception as exc:
            log.error("utm.list_sessions_failed", metadata={"reason": str(exc)})

        return sessions
