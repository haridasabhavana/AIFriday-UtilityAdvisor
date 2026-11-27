"""FastMCP stdio server exposing deterministic EnergyWise engine tools."""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from energywise.engines import tools

mcp = FastMCP("energywise-engines")


@mcp.tool()
def get_usage_summary(cust_ref: str, period: str = "30d") -> Dict[str, Any]:
    return tools.get_usage_summary(cust_ref, period)


@mcp.tool()
def get_tariff(cust_ref: str) -> Dict[str, Any]:
    return tools.get_tariff(cust_ref)


@mcp.tool()
def get_recommendation_candidates(cust_ref: str) -> List[Dict[str, Any]]:
    return tools.get_recommendation_candidates(cust_ref)


@mcp.tool()
def simulate_scenario(cust_ref: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return tools.simulate_scenario(cust_ref, actions)


@mcp.tool()
def forecast(cust_ref: str, actions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return tools.forecast(cust_ref, actions)


if __name__ == "__main__":
    mcp.run(transport="stdio")
