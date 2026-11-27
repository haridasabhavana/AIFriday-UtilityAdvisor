"""MCP client calling FastMCP stdio servers (with USE_MCP=0 direct-registry fallback)."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from energywise.config import BASE_DIR, USE_MCP
from energywise.engines.tools import REGISTRY

TOOL_SERVER_MAP = {
    "get_usage_summary": "energywise.mcp_servers.engines_server",
    "get_tariff": "energywise.mcp_servers.engines_server",
    "get_recommendation_candidates": "energywise.mcp_servers.engines_server",
    "simulate_scenario": "energywise.mcp_servers.engines_server",
    "forecast": "energywise.mcp_servers.engines_server",
    "search_kb": "energywise.mcp_servers.kb_server",
}


async def _call_stdio_mcp(module_name: str, tool_name: str, args: Dict[str, Any]) -> Any:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", module_name],
        cwd=str(BASE_DIR),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(tool_name, args)
            if res.content:
                text = getattr(res.content[0], "text", None)
                if text:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
            return {}


def call_tool(tool_name: str, args: Dict[str, Any], use_mcp: bool = USE_MCP) -> Any:
    """Execute an approved tool over FastMCP stdio (or direct REGISTRY if USE_MCP=0)."""
    if tool_name not in TOOL_SERVER_MAP:
        raise ValueError(f"Tool '{tool_name}' is not in the LLM-accessible MCP allowlist.")

    if use_mcp:
        try:
            return asyncio.run(_call_stdio_mcp(TOOL_SERVER_MAP[tool_name], tool_name, args))
        except Exception:
            # Safe fallback to in-process registry if stdio spawn fails in restricted environment
            pass

    fn = REGISTRY[tool_name]
    return fn(**args)
