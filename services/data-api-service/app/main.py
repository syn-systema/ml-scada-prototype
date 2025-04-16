"""
Data API Service for AI SCADA System
This service provides a REST API for accessing and manipulating data in the TimescaleDB and Memgraph databases.
It also subscribes to MQTT topics to receive real-time data from sensors.
"""

import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Query
from typing import List, Dict, Any

from .database import get_db, init_db
from .mqtt_handler import MQTTHandler
from .database import SessionLocal
from .routers import sensors, topology, alarms

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("data-api-service")

# Environment variables with defaults
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "api-service")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "api-service-password")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "data-api-service")
MQTT_TOPIC_SUBSCRIBE = os.getenv("MQTT_TOPIC_SUBSCRIBE", "ai_scada/data/#")

TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "tsdb")
TIMESCALE_PORT = int(os.getenv("TIMESCALE_PORT", 5432))
TIMESCALE_USER = os.getenv("TIMESCALE_USER", "scada")
TIMESCALE_PASSWORD = os.getenv("TIMESCALE_PASSWORD", "scadapassword")
TIMESCALE_DB = os.getenv("TIMESCALE_DB", "scada_timeseries")

MEMGRAPH_HOST = os.getenv("MEMGRAPH_HOST", "graphdb")
MEMGRAPH_PORT = int(os.getenv("MEMGRAPH_PORT", 7687))
MEMGRAPH_USER = os.getenv("MEMGRAPH_USER", "")  # Default is no auth for Memgraph
MEMGRAPH_PASSWORD = os.getenv("MEMGRAPH_PASSWORD", "")

# Global MQTT client and handler
mqtt_client = None
mqtt_handler = None

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC_SUBSCRIBE)
        logger.info(f"Subscribed to {MQTT_TOPIC_SUBSCRIBE}")
    else:
        logger.error(f"Failed to connect to MQTT broker with code {rc}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        logger.debug(f"Received message on topic {topic}: {payload}")
        
        # Process message using MQTT handler
        if mqtt_handler and topic.startswith("ai_scada/data/"):
            mqtt_handler.process_sensor_data(topic, payload)
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logger.warning("Unexpected disconnection from MQTT broker")
    else:
        logger.info("Disconnected from MQTT broker")

# Setup and teardown for MQTT client and database
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    logger.info("Initializing database models")
    init_db()
    
    # Startup: connect to MQTT broker
    global mqtt_client, mqtt_handler
    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    
    # Initialize MQTT handler
    mqtt_handler = MQTTHandler(mqtt_client, None)  # We don't need to pass SessionLocal anymore
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        logger.info(f"Starting MQTT client, connecting to {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
    
    yield
    
    # Shutdown: disconnect from MQTT broker
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("Disconnected from MQTT broker")

app = FastAPI(
    title="AI SCADA Data API",
    description="API for accessing and manipulating data in the AI SCADA system",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(sensors.router)
app.include_router(topology.router)
app.include_router(alarms.router)

@app.get("/")
async def root():
    """Root endpoint, returns basic service information."""
    return {
        "service": "AI SCADA Data API",
        "version": "0.1.0",
        "status": "operational"
    }

@app.get("/data/training/{table_name}", response_model=List[Dict[str, Any]], tags=["data"])
async def get_training_data(
    table_name: str,
    limit: int = Query(1000, ge=1, le=10000), 
    db: Session = Depends(get_db)
):
    """Fetches the last N records from a specified table for training.
    
    Security Note: Only allows fetching from 'sensor_data' or 'simulated_data'.
    """
    # Security check: Only allow specific tables
    allowed_tables = {"sensor_data", "simulated_data"}
    if table_name not in allowed_tables:
        raise HTTPException(
            status_code=403,
            detail=f"Access to table '{table_name}' is forbidden."
        )

    try:
        # Use text() for safe table name interpolation (even though we check above)
        # and parameter binding for limit
        query = text(
            f"""
            SELECT timestamp, sensor_id, value 
            FROM {table_name}
            ORDER BY timestamp DESC 
            LIMIT :limit
            """
        )
        logger.info(f"Executing query for training data from {table_name} with limit {limit}")
        # Execute query using SQLAlchemy session
        results = db.execute(query, {"limit": limit}).mappings().all()
        logger.info(f"Fetched {len(results)} records from {table_name}")
        return results
    except Exception as e:
        logger.error(f"Error fetching training data from table {table_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching data.")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # TODO: Add actual health checks for MQTT and database connections
    return {"status": "healthy"}
