"""
Router for topology-related API endpoints.
Handles operations on the graph database (Memgraph).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from ..database import get_graph_db

router = APIRouter(
    prefix="/topology",
    tags=["topology"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class NodeBase(BaseModel):
    labels: List[str]
    properties: Dict[str, Any]

class RelationshipBase(BaseModel):
    type: str
    properties: Dict[str, Any]
    source_id: str
    target_id: str

class NodeCreate(NodeBase):
    pass

class NodeResponse(NodeBase):
    id: str

class RelationshipCreate(RelationshipBase):
    pass

class RelationshipResponse(RelationshipBase):
    id: str

@router.get("/", response_model=Dict[str, Any])
def get_topology():
    """
    Get the complete system topology.
    Returns nodes and relationships in the graph.
    """
    graph_db = get_graph_db()
    
    # Get all nodes
    nodes_query = "MATCH (n) RETURN n"
    nodes_result = graph_db.execute_query(nodes_query)
    
    # Get all relationships
    rels_query = "MATCH (a)-[r]->(b) RETURN r, ID(a) as source_id, ID(b) as target_id"
    rels_result = graph_db.execute_query(rels_query)
    
    # Format response
    nodes = []
    for node_data in nodes_result:
        if 'n' in node_data:
            node = node_data['n']
            nodes.append({
                "id": node.id,
                "labels": list(node.labels),
                "properties": dict(node)
            })
    
    relationships = []
    for rel_data in rels_result:
        if 'r' in rel_data:
            rel = rel_data['r']
            relationships.append({
                "id": rel.id,
                "type": rel.type,
                "properties": dict(rel),
                "source_id": rel_data.get('source_id'),
                "target_id": rel_data.get('target_id')
            })
    
    return {
        "nodes": nodes,
        "relationships": relationships
    }

@router.get("/sensors", response_model=List[Dict[str, Any]])
def get_sensor_nodes():
    """
    Get all sensor nodes from the graph database.
    """
    graph_db = get_graph_db()
    
    query = "MATCH (s:Sensor) RETURN s"
    result = graph_db.execute_query(query)
    
    sensors = []
    for data in result:
        if 's' in data:
            sensor = data['s']
            sensors.append({
                "id": sensor.id,
                "labels": list(sensor.labels),
                "properties": dict(sensor)
            })
    
    return sensors

@router.get("/equipment", response_model=List[Dict[str, Any]])
def get_equipment_nodes():
    """
    Get all equipment nodes from the graph database.
    """
    graph_db = get_graph_db()
    
    query = "MATCH (e:Equipment) RETURN e"
    result = graph_db.execute_query(query)
    
    equipment = []
    for data in result:
        if 'e' in data:
            equip = data['e']
            equipment.append({
                "id": equip.id,
                "labels": list(equip.labels),
                "properties": dict(equip)
            })
    
    return equipment

@router.post("/nodes", response_model=Dict[str, Any])
def create_node(node: NodeCreate):
    """
    Create a new node in the graph database.
    """
    graph_db = get_graph_db()
    
    # Build Cypher query
    labels_str = ':'.join(node.labels)
    properties_str = ', '.join([f"{k}: ${k}" for k in node.properties.keys()])
    
    query = f"CREATE (n:{labels_str} {{{properties_str}}}) RETURN n"
    result = graph_db.execute_query(query, node.properties)
    
    if not result or 'n' not in result[0]:
        raise HTTPException(status_code=500, detail="Failed to create node")
    
    created_node = result[0]['n']
    return {
        "id": created_node.id,
        "labels": list(created_node.labels),
        "properties": dict(created_node)
    }

@router.post("/relationships", response_model=Dict[str, Any])
def create_relationship(relationship: RelationshipCreate):
    """
    Create a new relationship between nodes in the graph database.
    """
    graph_db = get_graph_db()
    
    # Build Cypher query
    properties_str = ', '.join([f"{k}: ${k}" for k in relationship.properties.keys()])
    
    query = f"""
    MATCH (a), (b)
    WHERE ID(a) = $source_id AND ID(b) = $target_id
    CREATE (a)-[r:{relationship.type} {{{properties_str}}}]->(b)
    RETURN r, ID(a) as source_id, ID(b) as target_id
    """
    
    params = {
        "source_id": relationship.source_id,
        "target_id": relationship.target_id,
        **relationship.properties
    }
    
    result = graph_db.execute_query(query, params)
    
    if not result or 'r' not in result[0]:
        raise HTTPException(status_code=500, detail="Failed to create relationship")
    
    created_rel = result[0]['r']
    return {
        "id": created_rel.id,
        "type": created_rel.type,
        "properties": dict(created_rel),
        "source_id": result[0].get('source_id'),
        "target_id": result[0].get('target_id')
    }

@router.get("/paths", response_model=Dict[str, Any])
def find_paths(
    start_id: str = Query(..., description="ID of the start node"),
    end_id: str = Query(..., description="ID of the end node"),
    max_depth: int = Query(5, description="Maximum path depth")
):
    """
    Find paths between two nodes in the graph.
    """
    graph_db = get_graph_db()
    
    query = f"""
    MATCH path = shortestPath((a)-[*1..{max_depth}]->(b))
    WHERE ID(a) = $start_id AND ID(b) = $end_id
    RETURN path
    """
    
    params = {
        "start_id": start_id,
        "end_id": end_id
    }
    
    result = graph_db.execute_query(query, params)
    
    if not result:
        return {"paths": []}
    
    # Process path results
    paths = []
    for data in result:
        if 'path' in data:
            path = data['path']
            path_data = {
                "nodes": [],
                "relationships": []
            }
            
            # Extract nodes and relationships from path
            for node in path.nodes:
                path_data["nodes"].append({
                    "id": node.id,
                    "labels": list(node.labels),
                    "properties": dict(node)
                })
            
            for rel in path.relationships:
                path_data["relationships"].append({
                    "id": rel.id,
                    "type": rel.type,
                    "properties": dict(rel),
                    "source_id": rel.start_node.id,
                    "target_id": rel.end_node.id
                })
            
            paths.append(path_data)
    
    return {"paths": paths}
