FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV PHOENIX_COLLECTOR_ENDPOINT="http://phoenix.phoenix.svc.cluster.local:6006"
ENV PHOENIX_PROJECT_NAME="lab-5-mcp"

CMD ["python", "server.py"]
