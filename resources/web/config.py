import os

# config.py, a configuration file for index.py
RECORDS_PER_PAGE = int(os.environ.get("RECORDS_PER_PAGE", 15))
AIRPLANE_RECORDS_PER_PAGE = int(os.environ.get("AIRPLANE_RECORDS_PER_PAGE", 5))
ELASTIC_URL = os.environ.get("ELASTIC_URL", "http://elasticsearch:9200/agile_data_science")
CASSANDRA_HOST = os.environ.get("CASSANDRA_HOST", "cassandra")
CASSANDRA_PORT = int(os.environ.get("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.environ.get("CASSANDRA_KEYSPACE", "agile_data_science")
CASSANDRA_TABLE = os.environ.get("CASSANDRA_TABLE", "flight_delay_ml_response")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
PREDICTION_TOPIC = os.environ.get("PREDICTION_TOPIC", "flight-delay-ml-request")
PREDICTION_RESPONSE_TOPIC = os.environ.get("PREDICTION_RESPONSE_TOPIC", "flight-delay-ml-response")
