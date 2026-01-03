import os

# config.py, a configuration file for index.py
RECORDS_PER_PAGE = int(os.environ.get("RECORDS_PER_PAGE", 15))
AIRPLANE_RECORDS_PER_PAGE = int(os.environ.get("AIRPLANE_RECORDS_PER_PAGE", 5))
ELASTIC_URL = os.environ.get("ELASTIC_URL", "http://elasticsearch:9200/agile_data_science")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
PREDICTION_TOPIC = os.environ.get("PREDICTION_TOPIC", "flight-delay-ml-request")
PREDICTION_RESPONSE_TOPIC = os.environ.get("PREDICTION_RESPONSE_TOPIC", "flight-delay-ml-response")
