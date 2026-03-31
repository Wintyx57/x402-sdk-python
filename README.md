# x402-bazaar

Python SDK for [x402 Bazaar](https://x402.ai) — the autonomous API marketplace with automatic USDC payments.

## Quick Start

```bash
pip install x402-bazaar
```

```python
from x402_bazaar import X402Client

# Zero-config: auto-generates wallet on SKALE (gas-free)
client = X402Client()

# Search for APIs
results = client.search("weather")

# Call with auto-payment (402 detection + USDC payment + retry)
data = client.call("weather-api", params={"city": "Paris"})
print(data.data)
```

## Features

- **Auto-payment** — transparent HTTP 402 handling (detect, pay, retry)
- **Multi-chain** — Base, Polygon, SKALE (gas-free)
- **Wallet management** — auto-generate, import, AES-256-GCM encryption
- **Budget control** — daily/weekly/monthly spending limits
- **Async support** — native async/await with httpx
- **Type-safe** — full type hints, Pydantic models, py.typed
- **AI integrations** — LangChain and CrewAI tools out-of-the-box

## Configuration

```python
from x402_bazaar import X402Client

# Explicit wallet + chain
client = X402Client(
    private_key="0x...",
    chain="base",  # or "polygon", "skale"
    budget={"max": 5.0, "period": "daily"},
)

# From encrypted wallet
client = X402Client.from_encrypted("wallet.json", password="secret")
```

## Async Usage

```python
async with X402Client(private_key="0x...") as client:
    results = await client.search_async("jokes")
    data = await client.call_async("joke-api")
```

## LangChain Integration

```bash
pip install x402-bazaar[langchain]
```

```python
from x402_bazaar import X402Client
from x402_bazaar.integrations.langchain import X402SearchTool, X402CallTool

client = X402Client()
tools = [X402SearchTool(client=client), X402CallTool(client=client)]

# Use with any LangChain agent
from langchain.agents import initialize_agent
agent = initialize_agent(tools=tools, llm=llm)
agent.run("Find a joke API and get me a joke")
```

## CrewAI Integration

```bash
pip install x402-bazaar[crewai]
```

```python
from x402_bazaar import X402Client
from x402_bazaar.integrations.crewai import X402SearchTool, X402CallTool

client = X402Client()
agent = Agent(
    tools=[X402SearchTool(client=client), X402CallTool(client=client)],
    goal="Research data using paid APIs"
)
```

## Balance & Budget

```python
# Check USDC balance on all chains
balances = client.get_balance()
# {"base": 12.5, "polygon": 3.0, "skale": 5.0}

# Set spending limits
client.set_budget(max_daily=5.0)

# Check budget status
status = client.get_budget_status()
print(f"Spent: ${status.spent}, Remaining: ${status.remaining}")
```

## Supported Chains

| Chain | Gas Cost | Speed |
|-------|----------|-------|
| SKALE | Free (CREDITS) | ~1s |
| Base | ~$0.001 ETH | ~2s |
| Polygon | ~$0.001 POL | ~3s |

## License

MIT
