"""
MQTT handler for the Data API Service.
Handles MQTT message processing and publishing.
"""

import json
import logging
import paho.mqtt.client as mqtt
from datetime import datetime
from sqlalchemy.orm import Session
from . import models
from .database import get_db_context

# Configure logging
logger = logging.getLogger("data-api-service.mqtt")

class MQTTHandler:
    """
    Handler for MQTT operations.
    Processes incoming messages and publishes outgoing messages.
    """
    def __init__(self, client: mqtt.Client, db_session_maker):
        """
        Initialize the MQTT handler.
        
        Args:
            client: MQTT client instance
            db_session_maker: SQLAlchemy session maker
        """
        self.client = client
        self.db_session_maker = db_session_maker
        
    def process_sensor_data(self, topic: str, payload: str):
        """
        Process sensor data from MQTT message.
        
        Args:
            topic: MQTT topic
            payload: Message payload as string
        """
        try:
            # Parse topic to extract sensor ID
            # Expected format: ai_scada/data/{sensor_id}
            topic_parts = topic.split('/')
            if len(topic_parts) < 3 or topic_parts[0] != 'ai_scada' or topic_parts[1] != 'data':
                logger.warning(f"Invalid topic format: {topic}")
                return
            
            sensor_id = topic_parts[2]
            
            # Parse payload as JSON
            data = json.loads(payload)
            
            # Extract timestamp or use current time
            timestamp = data.get('timestamp')
            if timestamp:
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except ValueError:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()
            
            # Extract value and unit
            value = data.get('value')
            if value is None:
                logger.warning(f"No value in payload: {payload}")
                return
            
            unit = data.get('unit', '')
            sensor_type = data.get('type', 'unknown')
            
            # Extract quality if available
            quality = data.get('quality', 100)  # Default to 100 (good quality)
            
            # Store in database
            with get_db_context() as db:
                # Check if sensor exists, create if not
                sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
                if not sensor:
                    logger.info(f"Creating new sensor: {sensor_id}")
                    sensor = models.Sensor(
                        id=sensor_id,
                        name=data.get('name', f"Sensor {sensor_id}"),
                        description=data.get('description', ''),
                        location=data.get('location', ''),
                        type=sensor_type,
                        unit=unit,
                        min_value=data.get('min_value'),
                        max_value=data.get('max_value')
                    )
                    db.add(sensor)
                    db.commit()
                
                # If the sensor's unit is different from the incoming unit, update the sensor
                if sensor.unit != unit and unit:
                    logger.info(f"Updating sensor {sensor_id} unit from {sensor.unit} to {unit}")
                    sensor.unit = unit
                    db.commit()
                
                # Store the value directly (no conversion needed as we're using American units)
                stored_value = value
                
                # Create sensor data record
                sensor_data = models.SensorData(
                    sensor_id=sensor_id,
                    timestamp=timestamp,
                    value=stored_value,
                    quality=quality
                )
                db.add(sensor_data)
                db.commit()
                
                logger.debug(f"Stored sensor data: {sensor_id}, value: {stored_value} {sensor.unit}")
                
                # Check for alarm conditions
                self._check_alarm_conditions(db, sensor, stored_value)
                
                # Publish a confirmation message
                confirmation_topic = f"ai_scada/data/{sensor_id}/confirmation"
                confirmation_payload = {
                    "id": sensor_data.id,
                    "timestamp": timestamp.isoformat(),
                    "value": stored_value,
                    "unit": sensor.unit,
                    "status": "stored"
                }
                self.publish_message(confirmation_topic, confirmation_payload)
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON payload: {payload}")
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")
    
    def _check_alarm_conditions(self, db: Session, sensor: models.Sensor, value: float):
        """
        Check for alarm conditions based on sensor value.
        
        Args:
            db: Database session
            sensor: Sensor model instance
            value: Current sensor value
        """
        # Simple threshold-based alarms
        if sensor.min_value is not None and value < sensor.min_value:
            severity = 3  # Medium severity
            message = f"Value below minimum threshold: {value} < {sensor.min_value} {sensor.unit}"
            self._create_alarm(db, sensor.id, severity, message)
            
        if sensor.max_value is not None and value > sensor.max_value:
            severity = 3  # Medium severity
            message = f"Value above maximum threshold: {value} > {sensor.max_value} {sensor.unit}"
            self._create_alarm(db, sensor.id, severity, message)
    
    def _create_alarm(self, db: Session, sensor_id: str, severity: int, message: str):
        """
        Create an alarm record in the database.
        
        Args:
            db: Database session
            sensor_id: Sensor ID
            severity: Alarm severity (1-5)
            message: Alarm message
        """
        alarm = models.Alarm(
            sensor_id=sensor_id,
            severity=severity,
            message=message
        )
        db.add(alarm)
        db.commit()
        
        # Publish alarm to MQTT
        alarm_topic = f"alarms/{sensor_id}"
        alarm_payload = json.dumps({
            "id": alarm.id,
            "sensor_id": sensor_id,
            "timestamp": alarm.timestamp.isoformat(),
            "severity": severity,
            "message": message
        })
        self.client.publish(alarm_topic, alarm_payload)
        
        logger.info(f"Created alarm: {message}")
    
    def publish_message(self, topic: str, payload: dict):
        """
        Publish a message to an MQTT topic.
        
        Args:
            topic: MQTT topic
            payload: Message payload as dictionary
        """
        try:
            # Convert payload to JSON string
            payload_str = json.dumps(payload)
            
            # Publish message
            result = self.client.publish(topic, payload_str)
            
            # Check if publish was successful
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to publish message to {topic}: {mqtt.error_string(result.rc)}")
            else:
                logger.debug(f"Published message to {topic}: {payload_str}")
                
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
