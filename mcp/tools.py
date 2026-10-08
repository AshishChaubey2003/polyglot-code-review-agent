"""
MCP (Model Context Protocol) tool exposure -- DEFERRED per the master
prompt's phasing. Intended shape: expose `review_code` and
`propose_fix` as MCP tools so an external MCP client (an IDE, another
agent) can call this system's review/repair pipeline directly, reusing
services/review_service.py rather than duplicating orchestration logic.
Not implemented -- a genuine stub, not a fake server.
"""

from __future__ import annotations


class MCPNotImplementedError(Exception):
    pass


def register_mcp_tools(*args, **kwargs):
    raise MCPNotImplementedError(
        "MCP tool exposure is deferred. See this module's docstring for the intended shape."
    )
