FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Base system packages and developer essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    file \
    git \
    jq \
    less \
    libssl-dev \
    locales \
    openssh-client \
    pkg-config \
    procps \
    sudo \
    unzip \
    vim \
    wget \
    zip \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for Homebrew (required) with passwordless sudo
RUN useradd -m -s /bin/bash developer \
    && echo 'developer ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/developer

USER developer
WORKDIR /home/developer

# =============================================================================
# Homebrew
# =============================================================================
RUN NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

ENV PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:${PATH}"
ENV HOMEBREW_NO_AUTO_UPDATE=1

RUN brew install \
    fd \
    fzf \
    gh \
    ripgrep \
    tree \
    yq

# =============================================================================
# Python — uv (manages Python versions, venvs, and packages)
# =============================================================================
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/developer/.local/bin:${PATH}"

# Install Python versions; default to 3.12
RUN uv python install 3.12 3.11 \
    && ln -sf "$(uv python find 3.12)" ~/.local/bin/python3 \
    && ln -sf "$(uv python find 3.12)" ~/.local/bin/python

# =============================================================================
# Node.js — nvm (switch versions with: nvm install/use <version>)
# =============================================================================
ENV NVM_DIR="/home/developer/.nvm"

RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# Install Node versions; default to 22 LTS
RUN bash -c '. "$NVM_DIR/nvm.sh" && nvm install 22 && nvm install 20 && nvm alias default 22'

# Create a stable symlink so Node works in non-interactive shells
RUN bash -c '. "$NVM_DIR/nvm.sh" && ln -sf "$(dirname "$(nvm which default)")" "$NVM_DIR/default_bin"'
ENV PATH="/home/developer/.nvm/default_bin:${PATH}"

# =============================================================================
# Go — goenv (switch versions with: goenv install/global <version>)
# =============================================================================
ENV GOENV_ROOT="/home/developer/.goenv"

RUN git clone https://github.com/go-nv/goenv.git "$GOENV_ROOT"
ENV PATH="/home/developer/.goenv/bin:/home/developer/.goenv/shims:${PATH}"

# Install Go versions; default to 1.22.5
RUN goenv install 1.22.5 \
    && goenv install 1.21.12 \
    && goenv global 1.22.5 \
    && goenv rehash

# =============================================================================
# Rust — rustup (switch versions with: rustup default stable/nightly/1.xx)
# =============================================================================
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
ENV PATH="/home/developer/.cargo/bin:${PATH}"

# =============================================================================
# Cloud CLIs — AWS and Azure
# =============================================================================
USER root
RUN ARCH=$(uname -m) \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-${ARCH}.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip

RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && rm -rf /var/lib/apt/lists/*
USER developer

RUN mkdir -p /home/developer/.azure

# =============================================================================
# Shell configuration — ensure version managers work in interactive sessions
# =============================================================================
RUN cat >> ~/.bashrc <<'BASHRC'

# nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && source "$NVM_DIR/bash_completion"

# goenv
export GOENV_ROOT="$HOME/.goenv"
eval "$(goenv init -)"

# uv shell completions
eval "$(uv generate-shell-completion bash 2>/dev/null)"

# rustup shell completions
eval "$(rustup completions bash 2>/dev/null)"
BASHRC

# =============================================================================
# Workspace
# =============================================================================
RUN mkdir -p /home/developer/workspace
WORKDIR /home/developer/workspace

# =============================================================================
# Web terminal — ttyd + tmux (for containerized Claude Code sessions)
# =============================================================================
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    ttyd \
    && rm -rf /var/lib/apt/lists/*
USER developer

# =============================================================================
# Claude Code — installed via official installer (latest at build time)
# =============================================================================
RUN curl -fsSL https://claude.ai/install.sh | bash

# =============================================================================
# Playwright MCP — browser automation for Claude Code
# =============================================================================
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

USER root
RUN bash -c '. "$NVM_DIR/nvm.sh" && npm install -g @playwright/mcp' && \
    mkdir -p /ms-playwright && \
    bash -c '. "$NVM_DIR/nvm.sh" && npx --yes playwright install chromium --with-deps' && \
    chmod -R 777 /ms-playwright && \
    rm -rf /var/lib/apt/lists/*
USER developer

# =============================================================================
# fastembed model cache — pre-download so PostToolUse hooks start instantly
# =============================================================================
# The qdrant-websearch hook uses sentence-transformers/all-MiniLM-L6-v2 (384-dim).
# Without pre-caching, the first hook run triggers a 30+ second download which
# exceeds the 5-second hook timeout, causing silent failure.
RUN uvx --python 3.12 --with fastembed python -c "\
from fastembed import TextEmbedding; \
from pathlib import Path; \
cache = str(Path.home() / '.cache' / 'fastembed'); \
m = TextEmbedding('sentence-transformers/all-MiniLM-L6-v2', cache_dir=cache); \
list(m.embed(['warmup'])); \
print('fastembed model cached')"

# =============================================================================
# Base image complete — role-specific Dockerfiles extend from here
# =============================================================================
ENV BASH_ENV=/home/developer/.env
ENV DISABLE_AUTOUPDATER=1
