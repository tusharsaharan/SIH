FROM python:3.11-slim
# Attack-launcher container for the isolated vLAN sandbox (lab use only)
RUN pip install --no-cache-dir scapy requests
WORKDIR /tools
COPY attack_runner.py .
CMD ["python", "attack_runner.py"]
