FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PROJECT_HOME=/app
ENV CASS_DRIVER_NO_CYTHON=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the web application
COPY resources/web /app

EXPOSE 5001

CMD ["python", "predict_flask.py"]
