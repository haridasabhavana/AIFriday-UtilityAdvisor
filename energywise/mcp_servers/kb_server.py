"""FastMCP stdio server exposing approved Knowledge Base search."""

from typing import Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from energywise.engines import tools

mcp = FastMCP("energywise-kb")


@mcp.tool()
def search_kb(query: str, doc_type: Optional[str] = None) -> List[Dict[str, str]]:
    return tools.search_kb(query, doc_type)


if __name__ == "__main__":
    mcp.run(transport="stdio")
