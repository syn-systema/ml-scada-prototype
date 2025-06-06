"""
Database models for the Data API Service.
Defines SQLAlchemy models for TimescaleDB and schema for Memgraph.
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Sensor(Base):
    """
    Sensor model for TimescaleDB.
    Represents a physical or virtual sensor in the SCADA system.
    """
    __tablename__ = "sensors"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    location = Column(String, nullable=True)
    type = Column(String, nullable=False)  # e.g., temperature, pressure, flow
    unit = Column(String, nullable=False)  # e.g., C, bar, m3/s
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with SensorData
    data = relationship("SensorData", back_populates="sensor")
    
    def __repr__(self):
        return f"<Sensor(id='{self.id}', name='{self.name}', type='{self.type}')>"

class SensorData(Base):
    """
    SensorData model for TimescaleDB.
    Represents time-series data from sensors.
    This table will be converted to a TimescaleDB hypertable.
    """
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(String, ForeignKey("sensors.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    value = Column(Float, nullable=False)
    quality = Column(Integer, nullable=True)  # Optional data quality indicator
    
    # Relationship with Sensor
    sensor = relationship("Sensor", back_populates="data")
    
    def __repr__(self):
        return f"<SensorData(sensor_id='{self.sensor_id}', timestamp='{self.timestamp}', value={self.value})>"

class Alarm(Base):
    """
    Alarm model for TimescaleDB.
    Represents alarms generated by the system.
    """
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(String, ForeignKey("sensors.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    severity = Column(Integer, nullable=False)  # 1-5, where 5 is most severe
    message = Column(String, nullable=False)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Alarm(id={self.id}, sensor_id='{self.sensor_id}', severity={self.severity})>"

# Memgraph schema definitions (for documentation purposes)
"""
Memgraph (Graph DB) Schema:

Nodes:
- Sensor: Represents a sensor in the system
  Properties: id, name, type, location
  
- Equipment: Represents physical equipment
  Properties: id, name, type, status
  
- Process: Represents a process or subsystem
  Properties: id, name, description
  
- Site: Represents a physical location or site
  Properties: id, name, location

Relationships:
- CONNECTED_TO: Connects sensors to equipment or other sensors
  Properties: connection_type
  
- PART_OF: Indicates that equipment is part of a process
  Properties: role
  
- LOCATED_IN: Indicates that a sensor or equipment is located in a site
  Properties: position
  
- DEPENDS_ON: Indicates that a process depends on another process
  Properties: dependency_type
"""
