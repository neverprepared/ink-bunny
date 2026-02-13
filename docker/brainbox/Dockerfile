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
# Claude Code — installed via npm (unpinned, latest at build time)
# =============================================================================
RUN bash -c '. "$NVM_DIR/nvm.sh" && npm install -g @anthropic-ai/claude-code'

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
# Claude Code configuration — pre-configure for container/headless use
# =============================================================================
ENV BASH_ENV=/home/developer/.env
ENV DISABLE_AUTOUPDATER=1

# Bake Claude config into image
COPY --chown=developer:developer docker/brainbox/setup/CLAUDE.md /home/developer/.claude/CLAUDE.md
COPY --chown=developer:developer docker/brainbox/setup/settings.json /home/developer/.claude/settings.json

# =============================================================================
# Skills — infrastructure (cloud) and development patterns from reflex
# =============================================================================

# Infrastructure / Cloud
COPY --chown=developer:developer reflex/plugins/reflex/skills/aws-patterns/SKILL.md /home/developer/.claude/skills/aws-patterns/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/azure-resource-discovery/SKILL.md /home/developer/.claude/skills/azure-resource-discovery/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/terraform-patterns/SKILL.md /home/developer/.claude/skills/terraform-patterns/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/kubernetes-patterns/SKILL.md /home/developer/.claude/skills/kubernetes-patterns/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/docker-patterns/SKILL.md /home/developer/.claude/skills/docker-patterns/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/observability-patterns/SKILL.md /home/developer/.claude/skills/observability-patterns/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/database-migration-patterns/SKILL.md /home/developer/.claude/skills/database-migration-patterns/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/n8n-patterns/SKILL.md /home/developer/.claude/skills/n8n-patterns/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/qdrant-patterns/SKILL.md /home/developer/.claude/skills/qdrant-patterns/SKILL.md

# Development
COPY --chown=developer:developer reflex/plugins/reflex/skills/agent-builder/SKILL.md /home/developer/.claude/skills/agent-builder/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/workflow-builder/SKILL.md /home/developer/.claude/skills/workflow-builder/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/router-builder/SKILL.md /home/developer/.claude/skills/router-builder/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/mcp-server-builder/SKILL.md /home/developer/.claude/skills/mcp-server-builder/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/workspace-builder/SKILL.md /home/developer/.claude/skills/workspace-builder/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/project-onboarding/SKILL.md /home/developer/.claude/skills/project-onboarding/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/task-decomposition/SKILL.md /home/developer/.claude/skills/task-decomposition/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/analysis-patterns/SKILL.md /home/developer/.claude/skills/analysis-patterns/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/rag-builder/SKILL.md /home/developer/.claude/skills/rag-builder/SKILL.md
COPY --chown=developer:developer reflex/plugins/reflex/skills/rag-wrapper/SKILL.md /home/developer/.claude/skills/rag-wrapper/SKILL.md

# Register MCP servers
# Playwright — browser automation (pre-installed above)
RUN bash -c '. "$NVM_DIR/nvm.sh" && claude mcp add playwright -- npx @playwright/mcp --headless --browser chromium --no-sandbox'
# Fetch — HTTP requests
RUN bash -c '. "$NVM_DIR/nvm.sh" && claude mcp add fetch -- npx -y @anthropic-ai/mcp-fetch'
# Memory — persistent key-value context
RUN bash -c '. "$NVM_DIR/nvm.sh" && claude mcp add memory -- npx -y @modelcontextprotocol/server-memory'
# Filesystem — scoped file access
RUN bash -c '. "$NVM_DIR/nvm.sh" && claude mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem /home/developer/workspace'
# GitHub — repos, issues, PRs (needs GITHUB_TOKEN at runtime)
RUN bash -c '. "$NVM_DIR/nvm.sh" && claude mcp add github -- npx -y @modelcontextprotocol/server-github'
# Brave Search — web search (needs BRAVE_API_KEY at runtime)
RUN bash -c '. "$NVM_DIR/nvm.sh" && claude mcp add brave-search -- npx -y @anthropic-ai/mcp-brave-search'
# Qdrant — vector database for RAG (needs QDRANT_URL at runtime)
RUN bash -c '. "$NVM_DIR/nvm.sh" && claude mcp add qdrant -- uvx --python 3.12 --with fastembed mcp-server-qdrant'

# Skip onboarding so CLAUDE_CODE_OAUTH_TOKEN works without interactive login
RUN bash -c 'if [ -f /home/developer/.claude.json ]; then \
    jq ". + {hasCompletedOnboarding: true, bypassPermissionsModeAccepted: true}" /home/developer/.claude.json > /tmp/.claude.json.tmp && \
    mv /tmp/.claude.json.tmp /home/developer/.claude.json; \
    else echo "{\"hasCompletedOnboarding\":true,\"bypassPermissionsModeAccepted\":true}" > /home/developer/.claude.json; fi'

# Shell aliases and shortcuts (appended to existing .bashrc)
COPY --chown=developer:developer docker/brainbox/setup/.bashrc /tmp/.bashrc.extra
RUN cat /tmp/.bashrc.extra >> /home/developer/.bashrc && rm /tmp/.bashrc.extra

# ttyd wrapper script
COPY --chown=developer:developer docker/brainbox/setup/ttyd-wrapper.sh /home/developer/ttyd-wrapper.sh
RUN chmod +x /home/developer/ttyd-wrapper.sh

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD pgrep -x "claude" > /dev/null || exit 1

CMD ["/bin/bash", "-l"]
