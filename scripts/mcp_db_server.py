import json
import asyncio
import asyncpg

# 引入 mcp SDK
from mcp.server.sse import SseServerTransport
from mcp.server.fastmcp import FastMCP

DB_URL = "postgresql://postgres:postgres@43.139.215.55:5432/postgres"

# 创建 FastMCP Server (自带工具装饰器和 FastAPI 路由能力)
mcp_server = FastMCP("chuma-postgres-mcp")

async def get_db_connection():
    return await asyncpg.connect(DB_URL, timeout=10)

# ==========================================
# 注册 MCP 工具给大模型使用
# ==========================================

@mcp_server.tool()
async def list_tables() -> str:
    """列出数据库中所有可用的表名称"""
    conn = await get_db_connection()
    try:
        records = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
        )
        tables = [r['table_name'] for r in records]
        return json.dumps({"tables": tables}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        await conn.close()

@mcp_server.tool()
async def get_table_schema(table_name: str) -> str:
    """获取指定表的所有字段和数据类型"""
    conn = await get_db_connection()
    try:
        records = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = $1 ORDER BY ordinal_position;", 
            table_name
        )
        schema = [{"column": r['column_name'], "type": r['data_type']} for r in records]
        return json.dumps({"table": table_name, "schema": schema}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        await conn.close()

@mcp_server.tool()
async def execute_readonly_sql(sql: str) -> str:
    """执行大模型生成的只读SQL查询（自动限制返回条数防止内存溢出）"""
    # 基础的安全校验：拒绝写操作
    if any(kw in sql.upper() for kw in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT"]):
        return json.dumps({"error": "安全拦截：只允许执行 SELECT 语句。"}, ensure_ascii=False)
    
    conn = await get_db_connection()
    try:
        # 强制嵌套并限制返回行数为 50 行，保护大模型上下文长度
        safe_sql = f"SELECT * FROM ({sql}) AS sub LIMIT 50"
        records = await conn.fetch(safe_sql)
        
        # asyncpg.Record 转字典
        results = [dict(r) for r in records]
        return json.dumps({"rows_returned": len(results), "data": results}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": f"SQL执行错误: {str(e)}"}, ensure_ascii=False)
    finally:
        await conn.close()

# ==========================================
# 启动 FastMCP 服务
# ==========================================

if __name__ == "__main__":
    print("Start independent MCP Database Server (FastMCP SSE) on port 8005...")
    # 对于最新的 mcp SDK (1.28.1)，FastMCP 底层默认写死了 8000 端口，且通过 sys.argv 修改不总是生效。
    # 为了彻底绕过这个限制，我们直接获取 FastMCP 生成的 ASGI 应用，并使用 uvicorn 手动启动。
    
    import uvicorn
    # mcp > 1.0 的 FastMCP 通过 sse_app() 返回底层的 Starlette 应用实例
    asgi_app = mcp_server.sse_app()
    
    # 手动调用 uvicorn 启动，并强制绑定 8005 端口
    uvicorn.run(asgi_app, host="0.0.0.0", port=8005, log_level="info")

    # # 当我们需要指定端口且不想受限于默认行为时，最稳定的办法是回到原生的 mcp SDK 启动方式，或者使用它内部依赖的 run 参数
    # # mcp > 1.0 的 FastMCP 其实在后台也是去查 OS 环境，这里直接修改 sys.argv 让 FastMCP 内部的 argparse 感知到端口
    # import sys
    # sys.argv = ["mcp_db_server.py", "--port", "8005"]
    # # FastMCP.run() 默认是不接收 host/port kwargs 的
    # mcp_server.run(transport="sse")
