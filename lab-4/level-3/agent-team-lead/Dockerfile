FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py peers.json ./

ENV HOST=0.0.0.0 PORT=9100 \
    PUBLIC_URL=http://reliability-team-lead:9100 \
    PEERS_FILE=/app/peers.json
EXPOSE 9100
CMD ["python", "server.py"]
