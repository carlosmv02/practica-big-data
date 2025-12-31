#!/usr/bin/env python3
"""
Test script to publish a mock prediction to Kafka 'flight-delay-ml-response' topic.
This helps verify the Flask Socket.IO consumer and client without running the full Spark job.

Usage:
    python3 resources/test_kafka_prediction.py
"""

import json
import uuid
from kafka import KafkaProducer

def test_publish_prediction():
    """Publish a test prediction message to Kafka."""
    
    # Initialize Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        api_version=(0, 10),
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    # Create a test prediction message
    test_uuid = str(uuid.uuid4())
    test_prediction = {
        'UUID': test_uuid,
        'Origin': 'ATL',
        'Dest': 'SFO',
        'Carrier': 'AA',
        'FlightNum': '1234',
        'FlightDate': '2016-12-25',
        'DepDelay': 5.0,
        'DayOfMonth': 25,
        'DayOfWeek': 6,
        'DayOfYear': 360,
        'Distance': 2139.0,
        'Timestamp': '2025-12-31T14:41:31',
        'Prediction': 2  # Slightly Late (0-30 Minute Delay)
    }
    
    print("[Test] Publishing test prediction with UUID: {}".format(test_uuid))
    print("[Test] Message content: {}".format(json.dumps(test_prediction, indent=2)))
    
    try:
        # Send to the response topic
        producer.send('flight-delay-ml-response', test_prediction)
        producer.flush()
        print("[Test] Message published successfully!")
        print("[Test] You should see the result appear in the web browser within 2-3 seconds.")
        print("[Test] Check the browser console (F12 -> Console) for detailed socket.io debug messages.")
        
    except Exception as e:
        print("[Test] Error publishing message: {}".format(e))
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Kafka Prediction Test - Publishing Mock Prediction")
    print("=" * 60)
    print("\nMake sure:")
    print("  1. Kafka is running on localhost:9092")
    print("  2. The topic 'flight-delay-ml-response' exists")
    print("  3. Flask is running (python3 resources/web/predict_flask.py)")
    print("  4. You have the /flights/delays/predict_kafka page open in a browser")
    print("\nRunning test...\n")
    
    success = test_publish_prediction()
    
    if success:
        print("\n" + "=" * 60)
        print("Test completed! Check your browser for the prediction result.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Test failed! Check Kafka connection and logs.")
        print("=" * 60)
