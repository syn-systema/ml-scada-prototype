#!/usr/bin/env python3
"""
Pipeline Simulator for AI SCADA System
Generates simulated sensor data and publishes it to MQTT broker.
"""

import os
import json
import time
import random
import logging
import signal
import sys
from datetime import datetime
import paho.mqtt.client as mqtt
import numpy as np
import schedule
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pipeline-simulator")

# Environment variables with defaults
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "simulator")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "simulator-password")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "pipeline-simulator")
SIMULATION_INTERVAL = int(os.getenv("SIMULATION_INTERVAL", 5))  # seconds

# Define pipeline segments and sensors
PIPELINE_SEGMENTS = [
    {
        "id": "segment-1",
        "name": "Intake Section",
        "sensors": [
            {
                "id": "pressure-1",
                "name": "Intake Pressure",
                "type": "pressure",
                "unit": "PSI",
                "min_value": 7.25,  # 0.5 bar = ~7.25 PSI
                "max_value": 72.5,  # 5.0 bar = ~72.5 PSI
                "normal_range": (14.5, 43.5),  # 1.0-3.0 bar = ~14.5-43.5 PSI
                "noise_level": 1.45  # 0.1 bar = ~1.45 PSI
            },
            {
                "id": "flow-1",
                "name": "Intake Flow Rate",
                "type": "flow",
                "unit": "MCF/day",
                "min_value": 8.5,  # Converted and adjusted for industry standards
                "max_value": 85.0,
                "normal_range": (34.0, 51.0),
                "noise_level": 1.7
            },
            {
                "id": "temp-1",
                "name": "Intake Temperature",
                "type": "temperature",
                "unit": "°F",
                "min_value": 41.0,  # 5.0°C = 41°F
                "max_value": 86.0,  # 30.0°C = 86°F
                "normal_range": (59.0, 77.0),  # 15.0-25.0°C = 59-77°F
                "noise_level": 0.9  # Adjusted for Fahrenheit scale
            }
        ]
    },
    {
        "id": "segment-2",
        "name": "Main Pipeline",
        "sensors": [
            {
                "id": "pressure-2",
                "name": "Main Pressure",
                "type": "pressure",
                "unit": "PSI",
                "min_value": 7.25,  # 0.5 bar = ~7.25 PSI
                "max_value": 87.0,  # 6.0 bar = ~87.0 PSI
                "normal_range": (29.0, 58.0),  # 2.0-4.0 bar = ~29.0-58.0 PSI
                "noise_level": 1.45  # 0.1 bar = ~1.45 PSI
            },
            {
                "id": "flow-2",
                "name": "Main Flow Rate",
                "type": "flow",
                "unit": "MCF/day",
                "min_value": 8.5,  # Converted and adjusted for industry standards
                "max_value": 85.0,
                "normal_range": (34.0, 51.0),
                "noise_level": 1.7
            },
            {
                "id": "vibration-1",
                "name": "Pipeline Vibration",
                "type": "vibration",
                "unit": "mm/s",
                "min_value": 0.0,
                "max_value": 10.0,
                "normal_range": (0.0, 3.0),
                "noise_level": 0.2
            }
        ]
    },
    {
        "id": "segment-3",
        "name": "Output Section",
        "sensors": [
            {
                "id": "pressure-3",
                "name": "Output Pressure",
                "type": "pressure",
                "unit": "PSI",
                "min_value": 1.45,  # 0.1 bar = ~1.45 PSI
                "max_value": 58.0,  # 4.0 bar = ~58.0 PSI
                "normal_range": (7.25, 29.0),  # 0.5-2.0 bar = ~7.25-29.0 PSI
                "noise_level": 1.45  # 0.1 bar = ~1.45 PSI
            },
            {
                "id": "flow-3",
                "name": "Output Flow Rate",
                "type": "flow",
                "unit": "MCF/day",
                "min_value": 8.5,  # Converted and adjusted for industry standards
                "max_value": 85.0,
                "normal_range": (34.0, 51.0),
                "noise_level": 1.7
            },
            {
                "id": "temp-2",
                "name": "Output Temperature",
                "type": "temperature",
                "unit": "°F",
                "min_value": 41.0,  # 5.0°C = 41°F
                "max_value": 95.0,  # 35.0°C = 95°F
                "normal_range": (59.0, 77.0),  # 15.0-25.0°C = 59-77°F
                "noise_level": 0.9  # Adjusted for Fahrenheit scale
            }
        ]
    },
    {
        "id": "segment-4",
        "name": "Separation Vessel",
        "sensors": [
            {
                "id": "oil-production",
                "name": "Oil Production Rate",
                "type": "production",
                "unit": "barrels/day",
                "min_value": 50.0,
                "max_value": 200.0,
                "normal_range": (70.0, 120.0),
                "noise_level": 3.0
            },
            {
                "id": "water-production",
                "name": "Water Production Rate",
                "type": "production",
                "unit": "barrels/day",
                "min_value": 100.0,
                "max_value": 300.0,
                "normal_range": (120.0, 180.0),
                "noise_level": 5.0
            },
            {
                "id": "gas-production",
                "name": "Gas Production Rate",
                "type": "production",
                "unit": "MCF/day",
                "min_value": 20.0,
                "max_value": 100.0,
                "normal_range": (30.0, 60.0),
                "noise_level": 2.0
            },
            {
                "id": "water-cut",
                "name": "Water Cut",
                "type": "percentage",
                "unit": "%",
                "min_value": 40.0,
                "max_value": 80.0,
                "normal_range": (50.0, 70.0),
                "noise_level": 1.0
            }
        ]
    },
    {
        "id": "segment-5",
        "name": "Valve System",
        "sensors": [
            {
                "id": "valve-inlet",
                "name": "Inlet Valve Position",
                "type": "valve",
                "unit": "%",
                "min_value": 0.0,
                "max_value": 100.0,
                "normal_range": (60.0, 100.0),
                "noise_level": 0.5
            },
            {
                "id": "valve-gas",
                "name": "Gas Valve Position",
                "type": "valve",
                "unit": "%",
                "min_value": 0.0,
                "max_value": 100.0,
                "normal_range": (40.0, 60.0),
                "noise_level": 0.5
            },
            {
                "id": "valve-water",
                "name": "Water Valve Position",
                "type": "valve",
                "unit": "%",
                "min_value": 0.0,
                "max_value": 100.0,
                "normal_range": (60.0, 80.0),
                "noise_level": 0.5
            },
            {
                "id": "valve-oil",
                "name": "Oil Valve Position",
                "type": "valve",
                "unit": "%",
                "min_value": 0.0,
                "max_value": 100.0,
                "normal_range": (20.0, 30.0),
                "noise_level": 0.5
            }
        ]
    }
]

# Global variables
mqtt_client = None
running = True
anomaly_mode = False
anomaly_sensor = None
anomaly_start_time = None
anomaly_duration = 0

def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the MQTT broker."""
    logger.info("Connected to MQTT broker")
    logger.info("Simulator started, publishing data every %d seconds", SIMULATION_INTERVAL)

def on_disconnect(client, userdata, rc):
    """Callback for when the client disconnects from the MQTT broker."""
    logger.info("Disconnected from MQTT broker")
    if rc != 0:
        logger.error("Unexpected disconnection")

def generate_sensor_value(sensor, timestamp):
    """
    Generate a simulated sensor value.
    
    Args:
        sensor: Sensor configuration dictionary
        timestamp: Current timestamp
        
    Returns:
        dict: Sensor data with value
    """
    # Get normal range and noise level
    min_normal, max_normal = sensor["normal_range"]
    noise = sensor["noise_level"]
    
    # Check if we're in anomaly mode and this is the affected sensor
    if anomaly_mode and anomaly_sensor and sensor["id"] == anomaly_sensor["id"]:
        # Calculate how far into the anomaly we are (0.0 to 1.0)
        anomaly_progress = min(1.0, (timestamp - anomaly_start_time).total_seconds() / anomaly_duration)
        
        # Determine anomaly type based on sensor type
        if sensor["type"] == "pressure":
            # Pressure drop anomaly
            base_value = max_normal - (max_normal - sensor["min_value"]) * anomaly_progress * 0.8
        elif sensor["type"] == "flow":
            # Flow reduction anomaly
            base_value = max_normal - (max_normal - sensor["min_value"]) * anomaly_progress * 0.7
        elif sensor["type"] == "temperature":
            # Temperature spike anomaly
            base_value = min_normal + (sensor["max_value"] - min_normal) * anomaly_progress * 0.6
        elif sensor["type"] == "vibration":
            # Vibration spike anomaly
            base_value = max_normal + (sensor["max_value"] - max_normal) * anomaly_progress * 0.9
        elif sensor["type"] == "production":
            # Production drop anomaly
            base_value = max_normal - (max_normal - sensor["min_value"]) * anomaly_progress * 0.6
        elif sensor["type"] == "percentage" or sensor["type"] == "valve":
            # Percentage/valve anomaly: drift toward extreme
            if random.random() > 0.5:
                base_value = min_normal - (min_normal - sensor["min_value"]) * anomaly_progress * 0.7
            else:
                base_value = max_normal + (sensor["max_value"] - max_normal) * anomaly_progress * 0.7
        else:
            # Default anomaly: drift toward min value
            base_value = max_normal - (max_normal - sensor["min_value"]) * anomaly_progress * 0.5
    else:
        # Normal operation: value within normal range with some noise
        base_value = random.uniform(min_normal, max_normal)
    
    # Add noise
    value = base_value + random.uniform(-noise, noise)
    
    # Ensure value is within sensor's min/max range
    value = max(sensor["min_value"], min(sensor["max_value"], value))
    
    # Round to 2 decimal places for cleaner data
    value = round(value, 2)
    
    return {
        "sensor_id": sensor["id"],
        "name": sensor["name"],
        "type": sensor["type"],
        "unit": sensor["unit"],
        "value": value,
        "timestamp": timestamp.isoformat(),
        "quality": 100  # Default to good quality
    }

def publish_sensor_data():
    """
    Generate and publish sensor data for all pipeline segments.
    """
    timestamp = datetime.utcnow()
    
    for segment in PIPELINE_SEGMENTS:
        for sensor in segment["sensors"]:
            # Generate sensor data
            data = generate_sensor_value(sensor, timestamp)
            
            # Add segment information
            data["segment_id"] = segment["id"]
            data["segment_name"] = segment["name"]
            
            # Convert to JSON
            payload = json.dumps(data)
            
            # Publish to MQTT
            topic = f"ai_scada/data/{sensor['id']}"
            mqtt_client.publish(topic, payload)
            logger.debug(f"Published to {topic}: {payload}")
    
    # Log summary
    logger.info(f"Published data for {sum(len(segment['sensors']) for segment in PIPELINE_SEGMENTS)} sensors")
    
    # Check if we should end an anomaly
    global anomaly_mode, anomaly_sensor, anomaly_start_time, anomaly_duration
    if anomaly_mode and (datetime.utcnow() - anomaly_start_time).total_seconds() >= anomaly_duration:
        logger.info(f"Ending anomaly for sensor {anomaly_sensor['id']}")
        anomaly_mode = False
        anomaly_sensor = None

def start_anomaly():
    """
    Randomly start an anomaly on one sensor.
    """
    global anomaly_mode, anomaly_sensor, anomaly_start_time, anomaly_duration
    
    # Only start a new anomaly if not already in anomaly mode
    if not anomaly_mode:
        # Randomly select a segment and sensor
        segment = random.choice(PIPELINE_SEGMENTS)
        sensor = random.choice(segment["sensors"])
        
        # Set anomaly parameters
        anomaly_mode = True
        anomaly_sensor = sensor
        anomaly_start_time = datetime.utcnow()
        anomaly_duration = random.uniform(60, 300)  # 1-5 minutes
        
        logger.info(f"Starting anomaly for sensor {sensor['id']} in {segment['name']} for {anomaly_duration:.1f} seconds")

def signal_handler(sig, frame):
    """
    Handle termination signals.
    """
    global running
    logger.info("Stopping simulator...")
    running = False
    if mqtt_client:
        mqtt_client.disconnect()
    logger.info("Simulator stopped")
    sys.exit(0)

def main():
    """
    Main function to run the simulator.
    """
    global mqtt_client
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize MQTT client
    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    
    # Connect to MQTT broker
    logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        mqtt_client.loop_start()
        
        # Schedule data generation
        schedule.every(SIMULATION_INTERVAL).seconds.do(publish_sensor_data)
        
        # Schedule random anomalies (approximately once per hour)
        schedule.every(60 * 60 / 10).seconds.do(lambda: random.random() < 0.1 and start_anomaly())
        
        # Initial data publish
        publish_sensor_data()
        
        # Main loop
        while running:
            schedule.run_pending()
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in simulator: {e}")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            logger.info("Disconnected from MQTT broker")
            logger.info("Simulator stopped")

if __name__ == "__main__":
    main()
