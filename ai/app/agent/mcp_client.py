"""MCP 客户端 — 连接远程 MCP Server，获取工具并执行调用

使用 Streamable HTTP 传输协议（/mcp 端点）。
相比 SSE 传输，Streamable HTTP 每次请求都是独立的 HTTP POST，
无需维持长连接，更适合通过代理访问外网 MCP Server。

所有待连接的 MCP Server 通过 MCP_SERVER_URLS（逗号分隔列表）配置，
系统启动时自动遍历连接，无需修改代码。
"""
import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _resolve_proxy() -> str | None:
    """解析代理地址：优先 MCP_PROXY 配置，其次环境变量"""
    return (
        settings.MCP_PROXY
        or os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("HTTP_PROXY")
        or None
    )


def _url_to_server_name(url: str) -> str:
    """从 URL 提取 host:port 作为 server 名称"""
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    port = parsed.port
    return f"{host}:{port}" if port else host


class MCPClient:
    """封装 MCP 连接和工具调用

    支持同时连接多个 MCP Server (Search, Database 等)。
    在应用 lifespan 中通过 async with 管理连接生命周期。
    """

    def __init__(self):
        self._sessions: dict[str, Any] = {} # 存储 {server_name: ClientSession}
        self._tool_server_map: dict[str, str] = {}  # tool_name → server_name
        self._cm_stack: Any = None  # contextlib.AsyncExitStack

    @property
    def is_connected(self) -> bool:
        return len(self._sessions) > 0

    async def __aenter__(self):
        self._cm_stack = __import__("contextlib").AsyncExitStack()

        # 从配置读取所有待连接的 MCP Server URL，自动遍历连接
        urls = settings.get_mcp_server_urls()
        if not urls:
            logger.info("No MCP server URLs configured, skipping MCP initialization")
            return self

        token = settings.MCP_SEARCH_TOKEN or None
        seen_names: set[str] = set()

        for url in urls:
            server_name = _url_to_server_name(url)
            # 去重：同名 URL 追加序号
            base_name = server_name
            counter = 2
            while server_name in seen_names:
                server_name = f"{base_name}-{counter}"
                counter += 1
            seen_names.add(server_name)
            await self.connect_server(server_name, url, token)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect_server(self, server_name: str, url: str, token: str | None = None) -> bool:
        """连接指定的 MCP Server 并注册其工具"""
        if not url:
            logger.info(f"[{server_name}] MCP URL not configured, skipping")
            return False

        try:
            from mcp.client.session import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            proxy_url = _resolve_proxy()

            def httpx_factory(**kwargs: Any) -> httpx.AsyncClient:
                if proxy_url:
                    kwargs["proxy"] = proxy_url
                return httpx.AsyncClient(**kwargs)

            headers: dict[str, Any] = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            if self._cm_stack is None:
                self._cm_stack = __import__("contextlib").AsyncExitStack()

            # 使用 Streamable HTTP 传输（/mcp 端点），每次请求独立 HTTP POST
            streams = await self._cm_stack.enter_async_context(
                streamablehttp_client(url, headers=headers, httpx_client_factory=httpx_factory)
            )
            read_stream, write_stream = streams[0], streams[1]

            # 进入 ClientSession 上下文
            session = await self._cm_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            # 初始化会话
            await session.initialize()
            self._sessions[server_name] = session

            # 发现工具并注册到 ToolRegistry
            tools_result = await session.list_tools()
            from app.agent.tool_registry import ToolRegistry

            for tool in tools_result.tools:
                ToolRegistry.register_mcp_tool(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                )
                self._tool_server_map[tool.name] = server_name
                logger.info(f"[{server_name}] Discovered MCP tool: {tool.name}")

            logger.info(f"[{server_name}] MCP connected to {url}, {len(tools_result.tools)} tools discovered")
            return True

        except ImportError:
            logger.warning("mcp package not installed, MCP tools unavailable")
            return False
        except Exception as e:
            logger.error(f"[{server_name}] MCP connection failed: {e}")
            return False

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """调用 MCP Server 的工具 — 根据工具注册时的映射直接路由到正确的 server"""
        if not self._sessions:
            return "MCP 服务暂不可用（未连接）"

        # 查找工具归属的 server，直接路由
        server_name = self._tool_server_map.get(name)
        if server_name is None:
            return f"未找到工具 '{name}' 所属的 MCP Server"

        session = self._sessions.get(server_name)
        if session is None:
            return f"工具 '{name}' 所属的 MCP Server '{server_name}' 未连接"

        try:
            result = await asyncio.wait_for(
                session.call_tool(name, arguments),
                timeout=10.0,
            )

            # Extract text from content blocks
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif hasattr(block, "data"):
                    parts.append(str(block.data))
                else:
                    parts.append(str(block))
            return "\n".join(parts) if parts else "(empty result)"

        except asyncio.TimeoutError:
            return f"工具调用超时 (Server: {server_name})"
        except Exception as e:
            logger.error(f"MCP tool '{name}' on server '{server_name}' failed: {e}")
            return f"工具执行异常: {str(e)}"

    async def close(self):
        """关闭所有 MCP 连接"""
        if self._cm_stack:
            try:
                await self._cm_stack.aclose()
            except Exception:
                pass
            self._cm_stack = None
        self._sessions.clear()


# Global singleton
mcp_client = MCPClient()
