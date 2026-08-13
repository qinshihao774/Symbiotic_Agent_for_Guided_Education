"""Agent 本地工具集 — 放入 .py 文件即可自动注册"""
import importlib
import logging
import pkgutil

logger = logging.getLogger(__name__)

for _, module_name, _ in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{module_name}")
    logger.info(f"Loaded built-in tools from: {module_name}")