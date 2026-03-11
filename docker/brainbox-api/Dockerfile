FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY brainbox/pyproject.toml brainbox/uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source
COPY brainbox/src ./src

# Copy agent definitions (role prompts and JSON configs)
COPY brainbox/agents ./agents

EXPOSE 9999

CMD ["uv", "run", "python", "-m", "brainbox", "api", "--host", "0.0.0.0", "--port", "9999"]
