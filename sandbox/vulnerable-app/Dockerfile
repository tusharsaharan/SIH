FROM python:3.11-slim
# Deliberately vulnerable app for the attack sandbox (TRAINING TARGET - DO NOT DEPLOY)
RUN pip install --no-cache-dir flask flask-sqlalchemy
WORKDIR /app
COPY app.py .
EXPOSE 8080
CMD ["python", "app.py"]
