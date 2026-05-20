FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV PHOENIX_COLLECTOR_ENDPOINT="http://phoenix-svc.phoenix.svc.cluster.local:6006/v1/traces"
ENV PHOENIX_PROJECT_NAME="lab-5-mcp"

# --demo: pod-friendly loop that exercises tools on a 15s cadence so Phoenix
# has continuous traces. Drop --demo to run as a real MCP stdio server (only
# makes sense outside k8s, e.g. behind MCP Inspector).
CMD ["python", "server.py", "--demo"]
