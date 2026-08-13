"""工具注册与调度 — 统一管理本地工具和 MCP 远程工具"""
import logging
import re
import time

from app.agent.schemas import ToolDef, ToolExecutionResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册中心

    支持两种工具来源：
    1. 本地工具 — 通过 @ToolRegistry.register() 装饰器注册的 Python 函数
    2. MCP 工具 — 通过 ToolRegistry.register_mcp_tool() 注册的远程工具

    Usage:
        @ToolRegistry.register("search_kg", "查询知识图谱", {...})
        async def search_kg(user_id: int, query: str) -> str: ...

        ToolRegistry.register_mcp_tool("search_web", "联网搜索", {...})
    """
    _tools: dict[str, ToolDef] = {}
    _DISPLAY_NAMES = {
        "search_kg": "搜索课程知识库",
        "read_document": "阅读教材资料",
        "search_web": "搜索公开资料",
        "list_tables": "检查可用学习数据",
        "describe_table": "了解数据结构",
        "query_postgresql": "查询学习记录",
    }
    _PURPOSES = {
        "search_kg": "查找与问题相关的知识点和概念关系",
        "read_document": "从教材、课件和笔记中查找可靠依据",
        "search_web": "补充查询公开资料",
        "list_tables": "确认可以查询哪些学习数据",
        "describe_table": "确认学习数据的组织方式",
        "query_postgresql": "查询与当前问题相关的学习记录",
    }

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        parameters: dict,
        is_mcp: bool = False,
        display_name: str | None = None,
        purpose: str | None = None,
    ):
        """装饰器 — 注册本地工具处理函数"""
        def decorator(func):
            cls._tools[name] = ToolDef(
                name=name,
                description=description,
                parameters=parameters,
                handler=func,
                is_mcp=is_mcp,
                display_name=display_name,
                purpose=purpose,
            )
            logger.info(f"Registered local tool: {name}")
            return func
        return decorator

    @classmethod
    def register_mcp_tool(cls, name: str, description: str, parameters: dict):
        """注册 MCP 远程工具（无本地 handler，执行时分发到 MCP 客户端）"""
        cls._tools[name] = ToolDef(
            name=name,
            description=description,
            parameters=parameters,
            handler=None,
            is_mcp=True,
            display_name=cls._DISPLAY_NAMES.get(name),
            purpose=cls._PURPOSES.get(name),
        )
        logger.info(f"Registered MCP tool: {name}")

    @classmethod
    def get_definitions(cls) -> list[dict]:
        """返回所有工具的 OpenAI function-calling 格式定义"""
        return [tool.to_openai_format() for tool in cls._tools.values()]

    @classmethod
    async def execute(cls, name: str, arguments: dict, user_id: int) -> ToolExecutionResult:
        """执行工具并返回文本结果，自动截断超长内容

        Args:
            name: 工具名称
            arguments: 工具参数（LLM 返回的 JSON 对象）
            user_id: 当前用户 ID

        Returns:
            工具执行结果文本（截断后）
        """
        tool = cls._tools.get(name)
        if tool is None:
            return ToolExecutionResult(
                raw=f"未知工具: {name}",
                success=False,
                summary="无法使用所需工具",
                duration_ms=0,
                metrics={},
                error_code="TOOL_NOT_FOUND",
                error_message="所需工具当前不可用",
                retryable=False,
            )

        t0 = time.perf_counter()
        try:
            if tool.is_mcp:
                from app.agent.mcp_client import mcp_client
                result = await mcp_client.call_tool(name, arguments)
            elif tool.handler is not None:
                result = await tool.handler(user_id=user_id, **arguments)
            else:
                raise RuntimeError("工具没有配置处理器")

            elapsed = time.perf_counter() - t0
            result_str = str(result)
            failed = cls._looks_failed(result_str)
            lines = result_str.count("\n") + 1
            arg_preview = cls._format_args(arguments)
            result_preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
            logger.info(
                f"Tool {name}({arg_preview}) → {len(result_str)} chars, "
                f"{lines} lines, {elapsed:.2f}s: {result_preview}"
            )

            raw = cls._truncate_result(result_str)
            return ToolExecutionResult(
                raw=raw,
                success=not failed,
                summary=cls._result_summary(name, raw, failed),
                duration_ms=round(elapsed * 1000),
                metrics=cls._result_metrics(name, raw),
                error_code="TOOL_EXECUTION_FAILED" if failed else None,
                error_message="工具未能获取有效结果" if failed else None,
                retryable=failed,
            )
        except Exception as e:
            logger.error(f"Tool '{name}' execution failed: {e}")
            elapsed = time.perf_counter() - t0
            return ToolExecutionResult(
                raw=f"执行出错: {str(e)}",
                success=False,
                summary="工具执行未成功",
                duration_ms=round(elapsed * 1000),
                metrics={},
                error_code="TOOL_EXECUTION_ERROR",
                error_message="工具执行未成功，请稍后重试",
                retryable=True,
            )

    @classmethod
    def get_ui_presentation(cls, name: str, arguments: dict) -> dict:
        """返回经过白名单整理、适合直接展示给用户的工具信息。"""
        tool = cls._tools.get(name)
        display_name = (tool.display_name if tool else None) or cls._DISPLAY_NAMES.get(name) or "调用学习工具"
        purpose = (tool.purpose if tool else None) or cls._PURPOSES.get(name) or "获取回答所需的可靠信息"

        input_summary = []
        query = arguments.get("query")
        if isinstance(query, str) and query.strip():
            input_summary.append({"label": "关键词", "value": query.strip()[:120]})
        elif name == "describe_table" and isinstance(arguments.get("table_name"), str):
            input_summary.append({"label": "数据对象", "value": arguments["table_name"][:80]})

        return {
            "name": name,
            "display_name": display_name,
            "purpose": purpose,
            "input_summary": input_summary,
        }

    @staticmethod
    def _looks_failed(text: str) -> bool:
        prefixes = ("执行出错", "查询失败", "知识图谱查询失败", "文档检索失败", "未知工具")
        return text.startswith(prefixes)

    @staticmethod
    def _result_metrics(name: str, text: str) -> dict[str, int | str]:
        if name == "search_kg":
            match = re.search(r"共\s*(\d+)\s*个结果", text)
            if match:
                return {"result_count": int(match.group(1))}
        return {}

    @classmethod
    def _result_summary(cls, name: str, text: str, failed: bool) -> str:
        if failed:
            return "工具执行未成功"
        if text.startswith("未在知识图谱中找到"):
            return "暂未找到匹配的知识节点"
        metrics = cls._result_metrics(name, text)
        if "result_count" in metrics:
            return f"找到 {metrics['result_count']} 个相关知识节点"
        if name == "read_document":
            return "已获取相关教材内容"
        if name == "search_web":
            return "已获取相关公开资料"
        if name in {"list_tables", "describe_table", "query_postgresql"}:
            return "已获取相关学习数据"
        return "已获取相关结果"

    @staticmethod
    def _format_args(args: dict, max_len: int = 80) -> str:
        """格式化工具参数用于日志，超长自动截断"""
        if not args:
            return ""
        parts = []
        for k, v in args.items():
            s = str(v)
            if len(s) > max_len:
                s = s[:max_len] + "..."
            parts.append(f"{k}={s!r}")
        return ", ".join(parts)

    @staticmethod
    def _truncate_result(text: str, max_lines: int = 100) -> str:
        """截断超长内容"""
        lines = text.split("\n")
        if len(lines) <= max_lines:
            return text
        omitted = len(lines) - max_lines
        return "\n".join(lines[:max_lines]) + f"\n...（已截断，省略 {omitted} 行）"
