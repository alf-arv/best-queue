FROM python:3.9

LABEL org.opencontainers.image.authors="alf-arv"

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /data

COPY app.py .

CMD ["python3", "app.py"]
