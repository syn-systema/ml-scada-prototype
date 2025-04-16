"""
Database connections and utilities for the Data API Service.
Handles connections to TimescaleDB (PostgreSQL) and Memgraph (Graph DB).
"""

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from neo4j import GraphDatabase
from contextlib import contextmanager
from typing import Generator

# Configure logging
logger = logging.getLogger("data-api-service.database")

# Environment variables with defaults
TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "tsdb")
TIMESCALE_PORT = int(os.getenv("TIMESCALE_PORT", 5432))
TIMESCALE_USER = os.getenv("TIMESCALE_USER", "scada")
TIMESCALE_PASSWORD = os.getenv("TIMESCALE_PASSWORD", "scadapassword")
TIMESCALE_DB = os.getenv("TIMESCALE_DB", "scada_timeseries")

MEMGRAPH_HOST = os.getenv("MEMGRAPH_HOST", "graphdb")
MEMGRAPH_PORT = int(os.getenv("MEMGRAPH_PORT", 7687))
MEMGRAPH_USER = os.getenv("MEMGRAPH_USER", "")  # Default is no auth for Memgraph
MEMGRAPH_PASSWORD = os.getenv("MEMGRAPH_PASSWORD", "")

# TimescaleDB (PostgreSQL) connection
SQLALCHEMY_DATABASE_URL = f"postgresql://{TIMESCALE_USER}:{TIMESCALE_PASSWORD}@{TIMESCALE_HOST}:{TIMESCALE_PORT}/{TIMESCALE_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Memgraph connection
MEMGRAPH_URI = f"bolt://{MEMGRAPH_HOST}:{MEMGRAPH_PORT}"

# Database dependency for FastAPI
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Context manager for use in non-FastAPI functions
@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class GraphDB:
    """
    Wrapper for Neo4j/Memgraph driver operations.
    Provides methods for executing Cypher queries.
    """
    def __init__(self):
        """Initialize the GraphDB connection."""
        auth = None
        if MEMGRAPH_USER and MEMGRAPH_PASSWORD:
            auth = (MEMGRAPH_USER, MEMGRAPH_PASSWORD)
        
        try:
            self.driver = GraphDatabase.driver(MEMGRAPH_URI, auth=auth)
            logger.info(f"Connected to Memgraph at {MEMGRAPH_URI}")
        except Exception as e:
            logger.error(f"Failed to connect to Memgraph: {e}")
            self.driver = None
    
    def close(self):
        """Close the driver connection."""
        if self.driver:
            self.driver.close()
    
    def execute_query(self, query, parameters=None):
        """
        Execute a Cypher query and return the results.
        
        Args:
            query (str): Cypher query to execute
            parameters (dict, optional): Parameters for the query
            
        Returns:
            list: Results of the query
        """
        if not self.driver:
            logger.error("No connection to Memgraph")
            return []
        
        if parameters is None:
            parameters = {}
        
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters)
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Error executing Cypher query: {e}")
            return []

# Singleton instance of GraphDB
graph_db = None

def get_graph_db():
    """
    Get or create a GraphDB instance.
    
    Returns:
        GraphDB: A GraphDB instance
    """
    global graph_db
    if graph_db is None:
        graph_db = GraphDB()
    return graph_db

# Initialize database models
def init_db():
    """Initialize database models and create tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Initialized database models")
