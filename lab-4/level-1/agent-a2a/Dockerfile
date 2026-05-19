FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV HOST=0.0.0.0 PORT=9000 PUBLIC_URL=http://reliability-a2a:9000
EXPOSE 9000
CMD ["python", "server.py"]
