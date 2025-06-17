FROM python:3.12-slim

WORKDIR /app

COPY data/data.csv .

COPY .env .

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY fitness_assistant .

EXPOSE 5000


ENTRYPOINT ["/bin/sh", "-c", "python db_prep.py && gunicorn --bind 0.0.0.0:5000 app:app"]
