#!/bin/bash
set -e

echo "Waiting for Kafka to be ready..."
while ! nc -z kafka 9092; do
  sleep 1
done
echo "Kafka is ready!"

echo "Waiting for MongoDB to be ready..."
while ! nc -z mongodb 27017; do
  sleep 1
done
echo "MongoDB is ready!"

echo "Starting Spark job..."
/opt/bitnami/spark/bin/spark-submit \
  --packages org.mongodb.spark:mongo-spark-connector_2.12:10.4.1,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
  --conf spark.mongodb.write.connection.uri="mongodb://mongodb:27017" \
  --conf spark.mongodb.read.connection.uri="mongodb://mongodb:27017" \
  --class es.upm.dit.ging.predictor.MakePrediction \
  /opt/spark-apps/flight_prediction_2.12-0.1.jar
