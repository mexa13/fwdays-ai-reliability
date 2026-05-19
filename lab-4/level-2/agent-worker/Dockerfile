FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV HOST=0.0.0.0 PORT=9001 PUBLIC_URL=http://reliability-worker:9001 \
    QDRANT_URL=http://qdrant.qdrant.svc.cluster.local:6333 \
    QDRANT_COLLECTION=sre-runbooks
EXPOSE 9001
CMD ["python", "server.py"]
