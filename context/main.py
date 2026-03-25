from fastmcp import FastMCP
import os

context_port = int(os.getenv("CONTEXT_PORT", 3278))

mcp = FastMCP("Infobús MCP Server")


@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"


if __name__ == "__main__":
    mcp.run(transport="http", port=context_port)
