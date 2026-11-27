"""FastMCP stdio server exposing mock smart-meter sync (backend only; never called by LLM)."""

from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
from energywise.engines import tools

mcp = FastMCP("smart-meter")


@mcp.tool()
def fetch_intervals(meter_ref: str, days: int = 30) -> Dict[str, Any]:
    return tools.fetch_intervals(meter_ref, days)


if __name__ == "__main__":
    mcp.run(transport="stdio")
