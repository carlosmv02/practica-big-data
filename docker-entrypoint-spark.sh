#!/bin/bash
set -e

echo "Waiting for Kafka to be ready..."
for i in {1..30}; do
  if nc -z kafka 9092; then
    echo "Kafka is ready!"
    break
  fi
  echo "Waiting for Kafka... attempt $i/30"
  sleep 2
done

echo "Waiting for Cassandra to be ready..."
for i in {1..60}; do
  if nc -z cassandra 9042; then
    echo "Cassandra port is open, checking if CQL is ready..."
    # Give Cassandra extra time to initialize CQL
    sleep 5
    echo "Cassandra is ready!"
    break
  fi
  echo "Waiting for Cassandra... attempt $i/60"
  sleep 2
done

echo "Initializing Cassandra schema..."
# Wait a bit more to ensure Cassandra is fully ready
sleep 10
# Try to run the init script
cqlsh cassandra -f /opt/spark-apps/init-cassandra.cql || echo "Schema may already exist, continuing..."

echo "Starting Spark job..."
/opt/spark/bin/spark-submit \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.4.1,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  --conf spark.cassandra.connection.host=cassandra \
  --conf spark.cassandra.connection.port=9042 \
  --master spark://spark-master:7077 \
  --class es.upm.dit.ging.predictor.MakePrediction \
  /opt/spark-apps/flight_prediction_2.12-0.1.jar
