"""CrewAI integration — Tool wrappers for x402 Bazaar.

Install: pip install x402-bazaar[crewai]
"""

from __future__ import annotations

import json
from typing import Any

try:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field
except ImportError as e:
    raise ImportError(
        "CrewAI integration requires crewai. Install with: pip install x402-bazaar[crewai]"
    ) from e

from x402_bazaar.client import X402Client
from x402_bazaar.types import CallResult


def _format_call_result(result: CallResult) -> str:
    """Serialize a CallResult to a human-readable string for LLM consumption."""
    data_str = json.dumps(result.data, indent=2, default=str)
    if result.tx_hash:
        return f"{data_str}\n[Paid {result.payment_amount} USDC on {result.chain}]"
    if result.free_tier_used:
        return f"{data_str}\n[Free tier — no payment]"
    return data_str


class SearchInput(BaseModel):
    """Input for X402SearchTool."""

    query: str = Field(description="Search query for finding APIs")


class CallInput(BaseModel):
    """Input for X402CallTool."""

    service_id: str = Field(description="Service ID to call")
    params: str = Field(
        default="{}",
        description="JSON string of parameters to pass to the API",
    )


class X402SearchTool(BaseTool):
    """Search x402 Bazaar for APIs."""

    name: str = "x402_search"
    description: str = (
        "Search the x402 Bazaar marketplace for APIs by keyword. "
        "Returns matching APIs with IDs, names, descriptions, and prices."
    )
    args_schema: type[BaseModel] = SearchInput
    client: X402Client

    class Config:
        arbitrary_types_allowed = True

    def _run(self, query: str) -> str:
        results = self.client.search(query)
        if not results:
            return f"No APIs found for '{query}'"

        lines = [f"Found {len(results)} API(s):"]
        for svc in results[:10]:
            price_str = f"${svc.price_usdc}" if svc.price_usdc > 0 else "FREE"
            lines.append(f"- {svc.name} (id: {svc.id}): {svc.description[:100]} [{price_str}]")
        return "\n".join(lines)

    async def _arun(self, query: str) -> str:
        results = await self.client.search_async(query)
        if not results:
            return f"No APIs found for '{query}'"

        lines = [f"Found {len(results)} API(s):"]
        for svc in results[:10]:
            price_str = f"${svc.price_usdc}" if svc.price_usdc > 0 else "FREE"
            lines.append(f"- {svc.name} (id: {svc.id}): {svc.description[:100]} [{price_str}]")
        return "\n".join(lines)


class X402CallTool(BaseTool):
    """Call an API on x402 Bazaar with automatic USDC payment."""

    name: str = "x402_call"
    description: str = (
        "Call an API on x402 Bazaar. Payment is automatic via USDC. "
        "Input: service_id and optional params (JSON string). "
        "Returns: API response data."
    )
    args_schema: type[BaseModel] = CallInput
    client: X402Client

    class Config:
        arbitrary_types_allowed = True

    def _run(self, service_id: str, params: str = "{}") -> str:
        try:
            parsed_params: dict[str, Any] = (
                json.loads(params) if isinstance(params, str) else params
            )
            result = self.client.call(service_id, params=parsed_params)
            return _format_call_result(result)
        except Exception as e:
            return f"Error: {e}"

    async def _arun(self, service_id: str, params: str = "{}") -> str:
        try:
            parsed_params: dict[str, Any] = (
                json.loads(params) if isinstance(params, str) else params
            )
            result = await self.client.call_async(service_id, params=parsed_params)
            return _format_call_result(result)
        except Exception as e:
            return f"Error: {e}"
