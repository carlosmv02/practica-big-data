#!/usr/bin/env python3
"""
Test script to publish a mock prediction to Kafka 'flight-delay-ml-response' topic.
This helps verify the Flask Socket.IO consumer and client without running the full Spark job.

Usage:
    python3 resources/test_kafka_prediction.py [UUID]
    
    If UUID is provided, it will use that UUID (useful for testing a specific prediction request)
    If no UUID is provided, it will generate a random one
"""

import json
import uuid
import sys
from kafka import KafkaProducer

def test_publish_prediction(test_uuid=None):
    """Publish a test prediction message to Kafka."""
    
    # Initialize Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        api_version=(0, 10),
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    # Create a test prediction message
    if not test_uuid:
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
        'Timestamp': '2026-01-02T11:30:00',
        'Route': 'ATL-SFO',
        'Prediction': 2.0  # Slightly Late (0-30 Minute Delay)
    }
    
    print("[Test] Publishing test prediction with UUID: {}".format(test_uuid))
    print("[Test] Message content: {}".format(json.dumps(test_prediction, indent=2)))
    
    try:
        # Send to the response topic
        producer.send('flight-delay-ml-response', test_prediction)
        producer.flush()
        print("\n[Test] ✓ Message published successfully to Kafka!")
        print("[Test] ✓ Expected result: 'Slightly Late (0-30 Minute Delay)'")
        print("\n[Test] Now check:")
        print("  1. Flask logs should show: '[Kafka Consumer] Received message'")
        print("  2. Flask logs should show: '[Kafka Consumer] Emitting to room: {}'".format(test_uuid))
        print("  3. Browser console (F12) should show: '[Socket] Received prediction event'")
        print("  4. Web page should display: 'Slightly Late (0-30 Minute Delay)'")
        
    except Exception as e:
        print("[Test] ✗ Error publishing message: {}".format(e))
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("Socket.IO + Kafka Integration Test")
    print("=" * 70)
    print("\nThis script tests the complete flow:")
    print("  Kafka → Flask Consumer → Socket.IO → Browser Client")
    print("\nPrerequisites:")
    print("  ✓ Kafka running on localhost:9092")
    print("  ✓ Topic 'flight-delay-ml-response' exists")
    print("  ✓ Flask running: python3 resources/web/predict_flask.py")
    print("  ✓ Browser open at: http://localhost:5001/flights/delays/predict_kafka")
    print("=" * 70)
    
    test_uuid = None
    if len(sys.argv) > 1:
        test_uuid = sys.argv[1]
        print("\n[Test] Using provided UUID: {}".format(test_uuid))
        print("[Test] TIP: Submit the form in the browser first, copy the UUID from")
        print("[Test]      the response, then run: python3 resources/test_kafka_prediction.py <UUID>")
    else:
        print("\n[Test] No UUID provided, generating random UUID")
        print("[Test] TIP: To test with a specific prediction request, pass the UUID as argument")
    
    print("\nRunning test...\n")
    
    success = test_publish_prediction(test_uuid)
    
    if success:
        print("\n" + "=" * 70)
        print("✓ Test completed! Message sent to Kafka.")
        print("=" * 70)
        print("\nIf you don't see the result in the browser:")
        print("  1. Check Flask terminal for '[Kafka Consumer] Received message'")
        print("  2. Check browser console (F12) for Socket.IO connection status")
        print("  3. Hard refresh the page (Ctrl+Shift+R)")
        print("  4. Verify Socket.IO CDN loaded: https://cdn.socket.io/4.5.4/socket.io.min.js")
    else:
        print("\n" + "=" * 70)
        print("✗ Test failed! Check Kafka connection and logs.")
        print("=" * 70)
