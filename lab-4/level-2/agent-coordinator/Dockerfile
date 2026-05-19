FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV HOST=0.0.0.0 PORT=9002 PUBLIC_URL=http://reliability-coordinator:9002 \
    WORKER_URL=http://reliability-worker.a2a-lab.svc.cluster.local:9001
EXPOSE 9002
CMD ["python", "server.py"]
