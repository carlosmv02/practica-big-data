#!/bin/bash
set -euo pipefail

KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
CASSANDRA_HOST="${CASSANDRA_HOST:-cassandra}"
CASSANDRA_PORT="${CASSANDRA_PORT:-9042}"
CASSANDRA_KEYSPACE="${CASSANDRA_KEYSPACE:-agile_data_science}"
CASSANDRA_TABLE="${CASSANDRA_TABLE:-flight_delay_ml_response}"
PREDICTION_REQUEST_TOPIC="${PREDICTION_REQUEST_TOPIC:-flight-delay-ml-request}"
PREDICTION_RESPONSE_TOPIC="${PREDICTION_RESPONSE_TOPIC:-flight-delay-ml-response}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-/tmp}"
MODEL_BASE_PATH="${MODEL_BASE_PATH:-/opt/models}"
MASTER_URL="${MASTER_URL:-spark://spark-master:7077}"

PACKAGES="org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3,com.datastax.spark:spark-cassandra-connector_2.12:3.5.0"

export MODEL_BASE_PATH
export KAFKA_BOOTSTRAP_SERVERS
export CASSANDRA_HOST
export CASSANDRA_PORT
export CASSANDRA_KEYSPACE
export CASSANDRA_TABLE
export PREDICTION_REQUEST_TOPIC
export PREDICTION_RESPONSE_TOPIC
export CHECKPOINT_DIR

# Ensure Ivy dirs exist (needed for --packages resolution inside containers)
mkdir -p /tmp/.ivy2/cache /tmp/.ivy2/jars

exec /opt/spark/bin/spark-submit \
  --class es.upm.dit.ging.predictor.MakePrediction \
  --master "${MASTER_URL}" \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  --conf "spark.cassandra.connection.host=${CASSANDRA_HOST}" \
  --conf "spark.cassandra.connection.port=${CASSANDRA_PORT}" \
  --packages "${PACKAGES}" \
  /opt/app/flight_prediction.jar
