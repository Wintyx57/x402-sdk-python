"""LangChain integration — BaseTool subclasses for x402 Bazaar.

Install: pip install x402-bazaar[langchain]
"""

from __future__ import annotations

from typing import Any

try:
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel, Field
except ImportError as e:
    raise ImportError(
        "LangChain integration requires langchain-core. "
        "Install with: pip install x402-bazaar[langchain]"
    ) from e

from x402_bazaar.client import X402Client


class SearchInput(BaseModel):
    """Input for X402SearchTool."""

    query: str = Field(description="Search query for finding APIs (e.g., 'weather', 'translation')")


class CallInput(BaseModel):
    """Input for X402CallTool."""

    service_id: str = Field(description="Service ID to call (from search results)")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters to pass to the API (e.g., {'city': 'Paris'})",
    )


class X402SearchTool(BaseTool):
    """Search x402 Bazaar marketplace for APIs.

    Finds APIs by keyword. Returns service IDs, names, descriptions, and prices.
    Use this to discover APIs before calling them with X402CallTool.
    """

    name: str = "x402_search"
    description: str = (
        "Search the x402 Bazaar API marketplace. "
        "Input a natural language query describing what you need "
        "(e.g. 'weather API', 'text translation', 'image generation'). "
        "Returns a list of available APIs with names, prices, and IDs. "
        "Use this BEFORE calling an API to find the right service_id."
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
        for svc in results[:10]:  # Top 10
            price_str = f"${svc.price_usdc}" if svc.price_usdc > 0 else "FREE"
            lines.append(
                f"- **{svc.name}** (id: `{svc.id}`): {svc.description[:100]} [{price_str}]"
            )
        return "\n".join(lines)

    async def _arun(self, query: str) -> str:
        results = await self.client.search_async(query)
        if not results:
            return f"No APIs found for '{query}'"

        lines = [f"Found {len(results)} API(s):"]
        for svc in results[:10]:
            price_str = f"${svc.price_usdc}" if svc.price_usdc > 0 else "FREE"
            lines.append(
                f"- **{svc.name}** (id: `{svc.id}`): {svc.description[:100]} [{price_str}]"
            )
        return "\n".join(lines)


class X402CallTool(BaseTool):
    """Call an API on x402 Bazaar with automatic payment.

    Payment is handled automatically — the tool detects HTTP 402,
    pays in USDC, and retries to get the response.
    """

    name: str = "x402_call"
    description: str = (
        "Call a paid API on x402 Bazaar. "
        "Requires a service_id (get it from search first) and optional params dict. "
        "Automatically handles USDC payment. "
        "Returns the API response data. "
        "Costs real USDC — search first to find the cheapest option."
    )
    args_schema: type[BaseModel] = CallInput
    client: X402Client

    class Config:
        arbitrary_types_allowed = True

    def _run(self, service_id: str, params: dict[str, Any] | None = None) -> str:
        try:
            result = self.client.call(service_id, params=params or {})
            import json

            data_str = json.dumps(result.data, indent=2, default=str)
            payment_info = ""
            if result.tx_hash:
                payment_info = (
                    f"\n[Paid {result.payment_amount} USDC on {result.chain}, tx: {result.tx_hash}]"
                )
            elif result.free_tier_used:
                payment_info = "\n[Free tier used — no payment required]"
            return f"{data_str}{payment_info}"
        except Exception as e:
            return f"Error calling {service_id}: {e}"

    async def _arun(self, service_id: str, params: dict[str, Any] | None = None) -> str:
        try:
            result = await self.client.call_async(service_id, params=params or {})
            import json

            data_str = json.dumps(result.data, indent=2, default=str)
            payment_info = ""
            if result.tx_hash:
                payment_info = (
                    f"\n[Paid {result.payment_amount} USDC on {result.chain}, tx: {result.tx_hash}]"
                )
            elif result.free_tier_used:
                payment_info = "\n[Free tier used — no payment required]"
            return f"{data_str}{payment_info}"
        except Exception as e:
            return f"Error calling {service_id}: {e}"
