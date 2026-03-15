FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

FROM base AS bot
CMD ["python", "-m", "src.main"]

FROM base AS mcp-server
CMD ["python", "-m", "src.mcp.server"]

FROM base AS mcp-http
ENV MCP_TRANSPORT=http
CMD ["python", "-m", "src.mcp.server"]
