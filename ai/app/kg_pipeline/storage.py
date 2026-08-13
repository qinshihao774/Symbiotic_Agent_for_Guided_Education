"""Apache AGE 持久化适配器

通过 PostgreSQL 协议操作 AGE 扩展的 Cypher 接口。
AGE 图数据模型：
  - Vertex label: Entity
    - Properties: id (str), name (str), type (str), description (str)
  - Edge label: RELATION
    - Properties: relationship_name (str), description (str)
"""

import logging
from typing import Optional

import networkx as nx
import psycopg2

from app.config import settings


logger = logging.getLogger(__name__)


class AgeConnectionError(Exception):
    """AGE 数据库连接失败"""
    pass


def _build_dsn() -> str:
    """从 settings 构建 PostgreSQL DSN"""
    return (
        f"host={settings.AGE_HOST} "
        f"port={settings.AGE_PORT} "
        f"dbname={settings.AGE_DB} "
        f"user={settings.AGE_USER} "
        f"password={settings.AGE_PASSWORD}"
    )


def _escape(value: str) -> str:
    """转义 Cypher 字符串中的单引号和反斜杠"""
    return value.replace("\\", "\\\\").replace("'", "\\'")


class AgeStorage:
    """Apache AGE 持久化适配器"""

    def __init__(self, dsn: Optional[str] = None, graph_name: Optional[str] = None):
        self._dsn = dsn or _build_dsn()
        if graph_name:
            self._graph_name = graph_name
        else:
            # 不再回退到 .env 中硬编码的 AGE_GRAPH_NAME（chuma_kg 已被删除），
            # 而是从数据库 kg_graphs 表解析真实存在的图谱。
            from app.kg_pipeline.graph_registry import resolve_default_graph
            self._graph_name = resolve_default_graph()

    def _get_conn(self):
        """创建 AGE 数据库连接"""
        try:
            conn = psycopg2.connect(self._dsn)
            conn.set_session(autocommit=True)
            return conn
        except psycopg2.OperationalError as e:
            raise AgeConnectionError(f"Cannot connect to AGE: {e}") from e

    def initialize_graph(self) -> None:
        """初始化 AGE 图（幂等）"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cur.execute("SELECT * FROM ag_catalog.create_graph(%s)", (self._graph_name,))
        except (psycopg2.errors.DuplicateObject, psycopg2.errors.InvalidSchemaName):
            logger.info(f"Graph '{self._graph_name}' already exists, skipping")
        except Exception as e:
            raise AgeConnectionError(
                f"Graph initialization failed for '{self._graph_name}': {e}"
            ) from e
        finally:
            conn.close()

    def write_graph(self, graph: nx.DiGraph) -> int:
        """将 NetworkX 图写入 AGE

        Args:
            graph: NetworkX DiGraph

        Returns:
            写入的边数
        """
        conn = self._get_conn()
        edge_count = 0

        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")

                for node_id, attrs in graph.nodes(data=True):
                    name = attrs.get("name", node_id)
                    ntype = attrs.get("type", "Concept")
                    desc = attrs.get("description", "")

                    cypher = (
                        f"SELECT * FROM cypher('{self._graph_name}', $$ "
                        f"MERGE (n:Entity {{id: '{_escape(node_id)}'}}) "
                        f"SET n.name = '{_escape(name)}', "
                        f"n.type = '{_escape(ntype)}', "
                        f"n.description = '{_escape(desc)}' "
                        f"$$) AS (n agtype);"
                    )
                    cur.execute(cypher)

                for src, dst, attrs in graph.edges(data=True):
                    rel_name = attrs.get("relationship_name", "related_to")
                    desc = attrs.get("description", "")

                    cypher = (
                        f"SELECT * FROM cypher('{self._graph_name}', $$ "
                        f"MATCH (a:Entity {{id: '{_escape(src)}'}}) "
                        f"MATCH (b:Entity {{id: '{_escape(dst)}'}}) "
                        f"CREATE (a)-[r:RELATION {{"
                        f"relationship_name: '{_escape(rel_name)}', "
                        f"description: '{_escape(desc)}'"
                        f"}}]->(b) "
                        f"$$) AS (r agtype);"
                    )
                    cur.execute(cypher)
                    edge_count += 1

        except psycopg2.Error as e:
            logger.error(f"AGE write failed: {e}")
            raise AgeConnectionError(f"AGE write failed: {e}") from e
        finally:
            conn.close()

        return edge_count

    def clear_graph(self) -> None:
        """清除当前图的所有数据"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cypher = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (n) DETACH DELETE n "
                    f"$$) AS (n agtype);"
                )
                cur.execute(cypher)
        except psycopg2.Error as e:
            logger.error(f"AGE clear failed: {e}")
            raise AgeConnectionError(f"AGE clear failed: {e}") from e
        finally:
            conn.close()

    def drop_graph(self) -> None:
        """删除当前 AGE 图（包括所有节点、边和图结构）"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cur.execute(
                    "SELECT * FROM ag_catalog.drop_graph(%s, true)",
                    (self._graph_name,),
                )
        except psycopg2.errors.UndefinedTable:
            logger.info(f"Graph '{self._graph_name}' does not exist, nothing to drop")
        except psycopg2.Error as e:
            logger.error(f"AGE drop failed: {e}")
            raise AgeConnectionError(f"AGE drop failed: {e}") from e
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 单条 CRUD — 供知识图谱编辑使用
    # ------------------------------------------------------------------

    def create_node(self, name: str, ntype: str = "Concept",
                    description: str = "") -> dict:
        """创建单个节点，返回 {node_id, name, type, description}"""
        import uuid as _uuid
        node_id = str(_uuid.uuid4())
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cypher = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"CREATE (n:Entity {{"
                    f"id: '{_escape(node_id)}', "
                    f"name: '{_escape(name)}', "
                    f"type: '{_escape(ntype)}', "
                    f"description: '{_escape(description)}'"
                    f"}}) "
                    f"RETURN n.id, n.name, n.type, n.description "
                    f"$$) AS (id agtype, name agtype, ntype agtype, desc agtype);"
                )
                cur.execute(cypher)
                row = cur.fetchone()
                if row is None:
                    raise AgeConnectionError("CREATE node returned no result")
                from app.kg_pipeline.queries import _strip_agtype
                return {
                    "node_id": _strip_agtype(row[0]),
                    "name": _strip_agtype(row[1]),
                    "type": _strip_agtype(row[2]),
                    "description": _strip_agtype(row[3]),
                }
        except psycopg2.Error as e:
            logger.error(f"AGE create_node failed: {e}")
            raise AgeConnectionError(f"AGE create_node failed: {e}") from e
        finally:
            conn.close()

    def update_node(self, node_id: str, **fields) -> dict:
        """更新节点属性（name/type/description），返回更新后的完整属性

        仅设置传入的字段，未传入的字段保持不变。
        """
        allowed = {"name", "type", "description"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            # 无需更新，直接返回当前值
            return self._get_node(node_id)

        set_clauses = ", ".join(
            f"n.{k} = '{_escape(v)}'" for k, v in updates.items()
        )
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cypher = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (n:Entity {{id: '{_escape(node_id)}'}}) "
                    f"SET {set_clauses} "
                    f"RETURN n.id, n.name, n.type, n.description "
                    f"$$) AS (id agtype, name agtype, ntype agtype, desc agtype);"
                )
                cur.execute(cypher)
                row = cur.fetchone()
                if row is None:
                    raise AgeConnectionError(
                        f"Node '{node_id}' not found for update"
                    )
                from app.kg_pipeline.queries import _strip_agtype
                return {
                    "node_id": _strip_agtype(row[0]),
                    "name": _strip_agtype(row[1]),
                    "type": _strip_agtype(row[2]),
                    "description": _strip_agtype(row[3]),
                }
        except psycopg2.Error as e:
            logger.error(f"AGE update_node failed: {e}")
            raise AgeConnectionError(f"AGE update_node failed: {e}") from e
        finally:
            conn.close()

    def _get_node(self, node_id: str) -> dict:
        """获取单个节点属性（内部辅助方法）"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cypher = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (n:Entity {{id: '{_escape(node_id)}'}}) "
                    f"RETURN n.id, n.name, n.type, n.description "
                    f"$$) AS (id agtype, name agtype, ntype agtype, desc agtype);"
                )
                cur.execute(cypher)
                row = cur.fetchone()
                if row is None:
                    raise AgeConnectionError(f"Node '{node_id}' not found")
                from app.kg_pipeline.queries import _strip_agtype
                return {
                    "node_id": _strip_agtype(row[0]),
                    "name": _strip_agtype(row[1]),
                    "type": _strip_agtype(row[2]),
                    "description": _strip_agtype(row[3]),
                }
        finally:
            conn.close()

    def delete_node(self, node_id: str) -> tuple[str, int]:
        """删除节点及其所有关联边，返回 (deleted_node_id, deleted_edge_count)"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")

                # 先统计关联边数
                cypher_count = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (n:Entity {{id: '{_escape(node_id)}'}})-[r]-() "
                    f"RETURN count(r) "
                    f"$$) AS (cnt agtype);"
                )
                cur.execute(cypher_count)
                row = cur.fetchone()
                from app.kg_pipeline.queries import _strip_agtype
                edge_count = int(_strip_agtype(row[0])) if row else 0

                # DETACH DELETE 同时删除节点和关联边
                cypher_del = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (n:Entity {{id: '{_escape(node_id)}'}}) "
                    f"DETACH DELETE n "
                    f"$$) AS (n agtype);"
                )
                cur.execute(cypher_del)
                return (node_id, edge_count)
        except psycopg2.Error as e:
            logger.error(f"AGE delete_node failed: {e}")
            raise AgeConnectionError(f"AGE delete_node failed: {e}") from e
        finally:
            conn.close()

    def create_edge(self, source_id: str, target_id: str,
                    relationship_name: str = "related_to",
                    description: str = "") -> dict:
        """创建边，返回 {source_node_id, target_node_id, relationship_name, description}

        如果 source 或 target 节点不存在，抛出 AgeConnectionError。
        如果边已存在，抛出 AgeConnectionError（由调用方转为 409）。
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")

                # 检查边是否已存在
                cypher_check = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (a:Entity {{id: '{_escape(source_id)}'}})"
                    f"-[r:RELATION]->"
                    f"(b:Entity {{id: '{_escape(target_id)}'}}) "
                    f"RETURN count(r) "
                    f"$$) AS (cnt agtype);"
                )
                cur.execute(cypher_check)
                row = cur.fetchone()
                from app.kg_pipeline.queries import _strip_agtype
                existing = int(_strip_agtype(row[0])) if row else 0
                if existing > 0:
                    raise AgeConnectionError(
                        f"Edge from '{source_id}' to '{target_id}' already exists"
                    )

                cypher = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (a:Entity {{id: '{_escape(source_id)}'}}) "
                    f"MATCH (b:Entity {{id: '{_escape(target_id)}'}}) "
                    f"CREATE (a)-[r:RELATION {{"
                    f"relationship_name: '{_escape(relationship_name)}', "
                    f"description: '{_escape(description)}'"
                    f"}}]->(b) "
                    f"RETURN a.id, b.id, r.relationship_name, r.description "
                    f"$$) AS (src agtype, tgt agtype, rel agtype, rel_desc agtype);"
                )
                cur.execute(cypher)
                row = cur.fetchone()
                if row is None:
                    raise AgeConnectionError(
                        f"CREATE edge failed: source '{source_id}' or target "
                        f"'{target_id}' not found"
                    )
                return {
                    "source_node_id": _strip_agtype(row[0]),
                    "target_node_id": _strip_agtype(row[1]),
                    "relationship_name": _strip_agtype(row[2]),
                    "description": _strip_agtype(row[3]),
                }
        except psycopg2.Error as e:
            logger.error(f"AGE create_edge failed: {e}")
            raise AgeConnectionError(f"AGE create_edge failed: {e}") from e
        finally:
            conn.close()

    def update_edge(self, source_id: str, target_id: str, **fields) -> dict:
        """更新边属性（relationship_name/description），返回更新后的完整属性"""
        allowed = {"relationship_name", "description"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self._get_edge(source_id, target_id)

        set_clauses = ", ".join(
            f"r.{k} = '{_escape(v)}'" for k, v in updates.items()
        )
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cypher = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (a:Entity {{id: '{_escape(source_id)}'}})"
                    f"-[r:RELATION]->"
                    f"(b:Entity {{id: '{_escape(target_id)}'}}) "
                    f"SET {set_clauses} "
                    f"RETURN a.id, b.id, r.relationship_name, r.description "
                    f"$$) AS (src agtype, tgt agtype, rel agtype, rel_desc agtype);"
                )
                cur.execute(cypher)
                row = cur.fetchone()
                if row is None:
                    raise AgeConnectionError(
                        f"Edge from '{source_id}' to '{target_id}' not found for update"
                    )
                from app.kg_pipeline.queries import _strip_agtype
                return {
                    "source_node_id": _strip_agtype(row[0]),
                    "target_node_id": _strip_agtype(row[1]),
                    "relationship_name": _strip_agtype(row[2]),
                    "description": _strip_agtype(row[3]),
                }
        except psycopg2.Error as e:
            logger.error(f"AGE update_edge failed: {e}")
            raise AgeConnectionError(f"AGE update_edge failed: {e}") from e
        finally:
            conn.close()

    def _get_edge(self, source_id: str, target_id: str) -> dict:
        """获取单条边属性（内部辅助方法）"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cypher = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (a:Entity {{id: '{_escape(source_id)}'}})"
                    f"-[r:RELATION]->"
                    f"(b:Entity {{id: '{_escape(target_id)}'}}) "
                    f"RETURN a.id, b.id, r.relationship_name, r.description "
                    f"$$) AS (src agtype, tgt agtype, rel agtype, rel_desc agtype);"
                )
                cur.execute(cypher)
                row = cur.fetchone()
                if row is None:
                    raise AgeConnectionError(
                        f"Edge from '{source_id}' to '{target_id}' not found"
                    )
                from app.kg_pipeline.queries import _strip_agtype
                return {
                    "source_node_id": _strip_agtype(row[0]),
                    "target_node_id": _strip_agtype(row[1]),
                    "relationship_name": _strip_agtype(row[2]),
                    "description": _strip_agtype(row[3]),
                }
        finally:
            conn.close()

    def delete_edge(self, source_id: str, target_id: str) -> tuple[str, str]:
        """删除边，返回 (source_id, target_id)"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cypher = (
                    f"SELECT * FROM cypher('{self._graph_name}', $$ "
                    f"MATCH (a:Entity {{id: '{_escape(source_id)}'}})"
                    f"-[r:RELATION]->"
                    f"(b:Entity {{id: '{_escape(target_id)}'}}) "
                    f"DELETE r "
                    f"RETURN a.id, b.id "
                    f"$$) AS (src agtype, tgt agtype);"
                )
                cur.execute(cypher)
                row = cur.fetchone()
                if row is None:
                    raise AgeConnectionError(
                        f"Edge from '{source_id}' to '{target_id}' not found for delete"
                    )
                from app.kg_pipeline.queries import _strip_agtype
                return (_strip_agtype(row[0]), _strip_agtype(row[1]))
        except psycopg2.Error as e:
            logger.error(f"AGE delete_edge failed: {e}")
            raise AgeConnectionError(f"AGE delete_edge failed: {e}") from e
        finally:
            conn.close()
