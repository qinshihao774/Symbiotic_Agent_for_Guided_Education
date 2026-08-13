"""知识图谱节点/边 CRUD 的请求/响应模型"""

from typing import Optional

from pydantic import BaseModel


# ---- 节点 ----

class NodeCreateRequest(BaseModel):
    graph_name: str
    name: str
    type: str = "Concept"
    description: str = ""


class NodeUpdateRequest(BaseModel):
    graph_name: str
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None


class NodeResponse(BaseModel):
    node_id: str
    name: str
    type: str
    description: str


class NodeDeleteResponse(BaseModel):
    deleted_node_id: str
    deleted_edge_count: int


# ---- 边 ----

class EdgeCreateRequest(BaseModel):
    graph_name: str
    source_node_id: str
    target_node_id: str
    relationship_name: str = "related_to"
    description: str = ""


class EdgeUpdateRequest(BaseModel):
    graph_name: str
    source_node_id: str
    target_node_id: str
    relationship_name: Optional[str] = None
    description: Optional[str] = None


class EdgeResponse(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_name: str
    description: str


class EdgeDeleteResponse(BaseModel):
    source_node_id: str
    target_node_id: str
