---
layout: default
title: Workspace Profile Switcher
---

# Workspace Profile Switcher

A terminal shell switcher using [direnv](https://direnv.net/) to manage workspace-specific environment variables and tool configurations.

## Install

```bash
brew install neverprepared/shell-profiler/shell-profiler
```

Or download a binary from the [releases page](https://github.com/neverprepared/shell-profiler/releases).

## Quick Start

```bash
# Create a new workspace profile
shell-profiler create my-project

# Navigate to the profile directory
cd profiles/my-project

# Allow direnv (first time only)
direnv allow

# Verify it's working
echo $WORKSPACE_PROFILE
```

## What It Does

When you enter a workspace directory, direnv automatically loads profile-specific settings:

- **Environment variables** for each workspace
- **Git configuration** (name, email, signing keys)
- **Tool configurations** (AWS, Kubernetes, Docker, etc.)
- **SSH settings** per workspace

This lets you seamlessly switch between personal, work, and client projects without manually reconfiguring anything.

## Supported Tools

| Tool | Environment Variable |
|------|---------------------|
| Git | `GIT_CONFIG_GLOBAL`, `GIT_SSH_COMMAND` |
| SSH | `SSH_AUTH_SOCK` |
| XDG | `XDG_CONFIG_HOME` |
| Kubernetes | `KUBECONFIG` |
| AWS | `AWS_PROFILE`, `AWS_CONFIG_FILE`, `AWS_SHARED_CREDENTIALS_FILE` |
| Google Cloud | `CLOUDSDK_CONFIG`, `GOOGLE_APPLICATION_CREDENTIALS` |
| Azure | `AZURE_CONFIG_DIR` |
| Docker | `DOCKER_CONFIG` |

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](GETTING-STARTED.md) | 5-minute quick start guide |
| [Installation](INSTALL.md) | direnv setup and shell hook configuration |
| [Quick Reference](QUICKSTART.md) | Common workflows and commands |
| [Project Summary](PROJECT-SUMMARY.md) | Architecture and technical overview |
| [Full README](https://github.com/neverprepared/shell-profiler#readme) | Complete reference documentation |

## Source

[github.com/neverprepared/shell-profiler](https://github.com/neverprepared/shell-profiler)
