"""
Router for alarm-related API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from .. import models
from ..database import get_db

router = APIRouter(
    prefix="/alarms",
    tags=["alarms"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class AlarmBase(BaseModel):
    sensor_id: str
    severity: int
    message: str

class AlarmCreate(AlarmBase):
    pass

class AlarmResponse(AlarmBase):
    id: int
    timestamp: datetime
    acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class AlarmAcknowledge(BaseModel):
    acknowledged_by: str

@router.get("/", response_model=List[AlarmResponse])
def get_alarms(
    skip: int = 0, 
    limit: int = 100,
    sensor_id: Optional[str] = None,
    min_severity: Optional[int] = None,
    acknowledged: Optional[bool] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Get a list of alarms with optional filtering.
    """
    query = db.query(models.Alarm)
    
    if sensor_id:
        query = query.filter(models.Alarm.sensor_id == sensor_id)
    if min_severity:
        query = query.filter(models.Alarm.severity >= min_severity)
    if acknowledged is not None:
        query = query.filter(models.Alarm.acknowledged == acknowledged)
    if start_time:
        query = query.filter(models.Alarm.timestamp >= start_time)
    if end_time:
        query = query.filter(models.Alarm.timestamp <= end_time)
        
    return query.order_by(models.Alarm.timestamp.desc()).offset(skip).limit(limit).all()

@router.post("/", response_model=AlarmResponse)
def create_alarm(alarm: AlarmCreate, db: Session = Depends(get_db)):
    """
    Create a new alarm.
    """
    # Check if sensor exists
    sensor = db.query(models.Sensor).filter(models.Sensor.id == alarm.sensor_id).first()
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    # Create alarm
    db_alarm = models.Alarm(
        sensor_id=alarm.sensor_id,
        severity=alarm.severity,
        message=alarm.message
    )
    db.add(db_alarm)
    db.commit()
    db.refresh(db_alarm)
    return db_alarm

@router.get("/{alarm_id}", response_model=AlarmResponse)
def get_alarm(alarm_id: int, db: Session = Depends(get_db)):
    """
    Get a specific alarm by ID.
    """
    alarm = db.query(models.Alarm).filter(models.Alarm.id == alarm_id).first()
    if alarm is None:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return alarm

@router.post("/{alarm_id}/acknowledge", response_model=AlarmResponse)
def acknowledge_alarm(
    alarm_id: int, 
    ack_data: AlarmAcknowledge,
    db: Session = Depends(get_db)
):
    """
    Acknowledge an alarm.
    """
    alarm = db.query(models.Alarm).filter(models.Alarm.id == alarm_id).first()
    if alarm is None:
        raise HTTPException(status_code=404, detail="Alarm not found")
    
    if alarm.acknowledged:
        raise HTTPException(status_code=400, detail="Alarm already acknowledged")
    
    alarm.acknowledged = True
    alarm.acknowledged_by = ack_data.acknowledged_by
    alarm.acknowledged_at = datetime.utcnow()
    
    db.commit()
    db.refresh(alarm)
    return alarm

@router.get("/summary/count", response_model=dict)
def get_alarm_count_summary(
    days: int = Query(7, description="Number of days to include in the summary"),
    db: Session = Depends(get_db)
):
    """
    Get a summary of alarm counts by severity.
    """
    start_time = datetime.utcnow() - timedelta(days=days)
    
    # Get counts by severity
    query = db.query(
        models.Alarm.severity,
        db.func.count(models.Alarm.id).label("count")
    ).filter(
        models.Alarm.timestamp >= start_time
    ).group_by(
        models.Alarm.severity
    )
    
    result = query.all()
    
    # Format result
    summary = {
        "total": sum(r.count for r in result),
        "by_severity": {r.severity: r.count for r in result},
        "acknowledged": 0,
        "unacknowledged": 0
    }
    
    # Get acknowledged/unacknowledged counts
    ack_query = db.query(
        models.Alarm.acknowledged,
        db.func.count(models.Alarm.id).label("count")
    ).filter(
        models.Alarm.timestamp >= start_time
    ).group_by(
        models.Alarm.acknowledged
    )
    
    ack_result = ack_query.all()
    
    for r in ack_result:
        if r.acknowledged:
            summary["acknowledged"] = r.count
        else:
            summary["unacknowledged"] = r.count
    
    return summary
