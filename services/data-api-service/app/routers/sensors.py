"""
Router for sensor-related API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from .. import models
from ..database import get_db
from pydantic import BaseModel, Field
from ..utils.unit_conversion import convert_value, get_unit_system, UnitSystem

router = APIRouter(
    prefix="/sensors",
    tags=["sensors"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class SensorBase(BaseModel):
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    type: str
    unit: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None

class SensorCreate(SensorBase):
    id: str

class SensorResponse(SensorBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SensorDataResponse(BaseModel):
    sensor_id: str
    timestamp: datetime
    value: float
    quality: Optional[int] = None
    unit: Optional[str] = None  # Add unit field to response

    class Config:
        from_attributes = True

class SensorDataWithUnitResponse(BaseModel):
    id: int
    sensor_id: str
    timestamp: datetime
    value: float
    quality: Optional[int] = None
    unit: str  # Unit information

    class Config:
        from_attributes = True

@router.get("/", response_model=List[SensorResponse])
def get_sensors(
    skip: int = 0, 
    limit: int = 100,
    type: Optional[str] = None,
    location: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get a list of sensors with optional filtering.
    """
    query = db.query(models.Sensor)
    
    if type:
        query = query.filter(models.Sensor.type == type)
    if location:
        query = query.filter(models.Sensor.location == location)
        
    return query.offset(skip).limit(limit).all()

@router.post("/", response_model=SensorResponse)
def create_sensor(sensor: SensorCreate, db: Session = Depends(get_db)):
    """
    Create a new sensor.
    """
    # Check if sensor already exists
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor.id).first()
    if db_sensor:
        raise HTTPException(status_code=400, detail="Sensor already exists")
    
    # Create new sensor
    db_sensor = models.Sensor(
        id=sensor.id,
        name=sensor.name,
        description=sensor.description,
        location=sensor.location,
        type=sensor.type,
        unit=sensor.unit,
        min_value=sensor.min_value,
        max_value=sensor.max_value
    )
    db.add(db_sensor)
    db.commit()
    db.refresh(db_sensor)
    return db_sensor

@router.get("/{sensor_id}", response_model=SensorResponse)
def get_sensor(sensor_id: str, db: Session = Depends(get_db)):
    """
    Get a specific sensor by ID.
    """
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return db_sensor

@router.put("/{sensor_id}", response_model=SensorResponse)
def update_sensor(sensor_id: str, sensor: SensorBase, db: Session = Depends(get_db)):
    """
    Update a sensor.
    """
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    # Update sensor attributes
    for key, value in sensor.dict().items():
        setattr(db_sensor, key, value)
    
    db_sensor.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_sensor)
    return db_sensor

@router.delete("/{sensor_id}")
def delete_sensor(sensor_id: str, db: Session = Depends(get_db)):
    """
    Delete a sensor.
    """
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    db.delete(db_sensor)
    db.commit()
    return {"message": f"Sensor {sensor_id} deleted"}

@router.get("/{sensor_id}/data")
def get_sensor_data(
    sensor_id: str, 
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get data for a specific sensor with optional time range filtering.
    Returns data with unit information.
    """
    # Check if sensor exists
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    # Build query
    query = db.query(models.SensorData).filter(models.SensorData.sensor_id == sensor_id)
    
    # Apply time range filters if provided
    if start_time:
        query = query.filter(models.SensorData.timestamp >= start_time)
    if end_time:
        query = query.filter(models.SensorData.timestamp <= end_time)
    
    # Get the data
    sensor_data = query.order_by(models.SensorData.timestamp.desc()).limit(limit).all()
    
    # Add unit information to each data point
    result = []
    for data in sensor_data:
        data_dict = {
            "id": data.id,
            "sensor_id": data.sensor_id,
            "timestamp": data.timestamp,
            "value": data.value,
            "quality": data.quality,
            "unit": db_sensor.unit
        }
        result.append(data_dict)
    
    return result

@router.get("/{sensor_id}/data/convert")
def get_sensor_data_with_conversion(
    sensor_id: str, 
    target_unit: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get data for a specific sensor with optional unit conversion.
    
    Args:
        sensor_id: ID of the sensor to get data for
        target_unit: Target unit to convert values to (if different from sensor's unit)
        start_time: Optional start time for filtering data
        end_time: Optional end time for filtering data
        limit: Maximum number of data points to return
    """
    # Check if sensor exists
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    # Build query
    query = db.query(models.SensorData).filter(models.SensorData.sensor_id == sensor_id)
    
    # Apply time range filters if provided
    if start_time:
        query = query.filter(models.SensorData.timestamp >= start_time)
    if end_time:
        query = query.filter(models.SensorData.timestamp <= end_time)
    
    # Get the data
    sensor_data = query.order_by(models.SensorData.timestamp.desc()).limit(limit).all()
    
    # Determine the unit to use
    source_unit = db_sensor.unit
    display_unit = target_unit if target_unit else source_unit
    
    # Add unit information to each data point, converting if necessary
    result = []
    for data in sensor_data:
        value = data.value
        
        # Convert value if target_unit is specified and different from sensor's unit
        if target_unit and target_unit != source_unit:
            try:
                value = convert_value(value, source_unit, target_unit)
            except Exception as e:
                # If conversion fails, use original value and log error
                print(f"Error converting value: {e}")
        
        data_dict = {
            "id": data.id,
            "sensor_id": data.sensor_id,
            "timestamp": data.timestamp,
            "value": value,
            "quality": data.quality,
            "unit": display_unit,
            "original_unit": source_unit
        }
        result.append(data_dict)
    
    return result

@router.post("/{sensor_id}/data", response_model=SensorDataWithUnitResponse)
def create_sensor_data(
    sensor_id: str,
    value: float = Query(..., description="Sensor reading value"),
    timestamp: Optional[datetime] = Query(None, description="Timestamp of the reading"),
    quality: Optional[int] = Query(None, description="Data quality indicator"),
    db: Session = Depends(get_db)
):
    """
    Create a new sensor data point.
    """
    # Check if sensor exists
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    # Use current time if timestamp not provided
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    # Create sensor data
    sensor_data = models.SensorData(
        sensor_id=sensor_id,
        timestamp=timestamp,
        value=value,
        quality=quality
    )
    
    db.add(sensor_data)
    db.commit()
    db.refresh(sensor_data)
    
    # Return with unit information
    response = {
        "id": sensor_data.id,
        "sensor_id": sensor_data.sensor_id,
        "timestamp": sensor_data.timestamp,
        "value": sensor_data.value,
        "quality": sensor_data.quality,
        "unit": db_sensor.unit
    }
    
    return response
