# x402-bazaar

[![PyPI version](https://badge.fury.io/py/x402-bazaar.svg)](https://pypi.org/project/x402-bazaar/)
[![CI](https://github.com/Wintyx57/x402-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/Wintyx57/x402-sdk-python/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Python SDK for [x402 Bazaar](https://x402.ai) — the autonomous API marketplace with automatic USDC payments.

**No other SDK combines crypto payments + API marketplace + AI agent tools in one package.**

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

That's it. The SDK handles wallet creation, payment detection, USDC transfers, and retries — all invisible.

## Features

- **Auto-payment** — transparent HTTP 402 handling (detect, pay, retry)
- **Multi-chain** — Base, Polygon (EIP-3009 gas-free), SKALE (gas-free)
- **Wallet management** — auto-generate, import, AES-256-GCM encryption
- **Budget control** — daily/weekly/monthly spending limits with auto-reset
- **Response validation** — HMAC-SHA256 signature verification + quality score check
- **Service protection** — auto-blacklist malicious/empty services (TTL-based)
- **Async native** — sync + async with httpx
- **Type-safe** — full type hints, Pydantic models, `py.typed` (PEP 561)
- **AI integrations** — LangChain and CrewAI tools out-of-the-box
- **Zero web3.py** — lightweight JSON-RPC client, no heavy dependencies

## Configuration

```python
from x402_bazaar import X402Client

# Explicit wallet + chain
client = X402Client(
    private_key="0x...",
    chain="base",               # "base", "polygon", "skale", "base-sepolia"
    budget={"max": 5.0, "period": "daily"},
    timeout=30,                  # seconds
    validation_secret="my-hmac-key",  # optional HMAC verification
)

# From encrypted wallet file
client = X402Client.from_encrypted("wallet.json", password="secret")

# Custom backend
client = X402Client(base_url="https://your-bazaar-instance.com")
```

## Async Usage

```python
async with X402Client(private_key="0x...") as client:
    results = await client.search_async("jokes")
    data = await client.call_async("joke-api")
    health = await client.health_async()
    balance = await client.get_balance_async()
```

All methods have an `_async` variant.

## API Reference

### Core Methods

| Method | Description |
|--------|-------------|
| `search(query)` | Search APIs by keyword |
| `list_services(page, limit)` | List all APIs with pagination |
| `get_service(service_id)` | Get service details |
| `call(service_id, params)` | Call API with auto-payment |
| `get_balance(chain?)` | Get USDC balance (one or all chains) |
| `health()` | Backend health check |

### Budget & Wallet

| Method | Description |
|--------|-------------|
| `set_budget(max_daily=5.0)` | Set spending limit |
| `get_budget_status()` | Check spent/remaining/period |
| `fund_wallet()` | Get funding instructions for your chain |
| `claim_faucet()` | Claim free SKALE CREDITS |

### Wallet Utilities

```python
from x402_bazaar import generate_wallet, encrypt_wallet, decrypt_wallet

wallet = generate_wallet()
print(wallet.address)  # 0x...

encrypt_wallet(wallet.private_key, "wallet.json", password="secret")
restored = decrypt_wallet("wallet.json", password="secret")
```

## Response Validation

The SDK can verify response integrity using HMAC-SHA256 signatures:

```python
client = X402Client(
    private_key="0x...",
    validation_secret="shared-secret",
)

# If the backend signs responses with the same secret,
# the SDK verifies automatically. Mismatches → service blacklisted.
```

Additionally, the SDK checks response quality: if a server claims high quality but returns empty data, the service is auto-blacklisted for 10 minutes.

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
researcher = Agent(
    tools=[X402SearchTool(client=client), X402CallTool(client=client)],
    goal="Research data using paid APIs"
)
```

## Balance & Budget

```python
# Check USDC balance on all chains
balances = client.get_balance()
# {"base": 12.5, "polygon": 3.0, "skale": 5.0, "base-sepolia": 0.0}

# Single chain
balance = client.get_balance(chain="base")
# {"base": 12.5}

# Set spending limits
client.set_budget(max_daily=5.0)
# or: max_weekly=25.0, max_monthly=100.0

# Check budget status
status = client.get_budget_status()
print(f"Spent: ${status.spent}, Remaining: ${status.remaining}, Calls: {status.call_count}")

# Get funding instructions
info = client.fund_wallet()
print(info["instructions"])
```

## Supported Chains

| Chain | Gas Cost | Speed | Notes |
|-------|----------|-------|-------|
| SKALE | Free (CREDITS) | ~1s | Best for getting started |
| Base | ~$0.001 ETH | ~2s | Coinbase ecosystem |
| Polygon | ~$0.001 POL | ~3s | EIP-3009 gas-free payments |
| Base Sepolia | Free (testnet) | ~1s | Testing only |

## Error Handling

```python
from x402_bazaar import X402Client
from x402_bazaar.exceptions import (
    InsufficientBalanceError,
    BudgetExceededError,
    ApiError,
    TimeoutError,
)

client = X402Client()

try:
    data = client.call("expensive-api")
except InsufficientBalanceError as e:
    print(f"Need {e.required} USDC, have {e.available}")
except BudgetExceededError as e:
    print(f"Budget limit: {e.limit} USDC ({e.period})")
except ApiError as e:
    print(f"API error {e.status_code}: {e}")
except TimeoutError as e:
    print(f"Timed out after {e.timeout_ms}ms")
```

## How Payment Works

1. `client.call("service")` sends a request with no payment headers
2. Backend returns **HTTP 402** with payment details (amount, recipient, chain)
3. SDK checks local budget limits
4. SDK checks on-chain USDC balance
5. SDK signs and sends USDC transfer (or EIP-3009 for Polygon)
6. SDK retries the request with `X-Payment-TxHash` header
7. Backend verifies payment on-chain and returns the API response

All of this happens in a single `client.call()` invocation.

## Development

```bash
git clone https://github.com/Wintyx57/x402-sdk-python.git
cd x402-sdk-python
pip install -e ".[dev]"

# Run unit tests
pytest tests/ -m "not integration" -v

# Run integration tests (requires internet)
pytest tests/ -m integration -v

# Run all tests
pytest tests/ -v

# Lint
ruff check x402_bazaar/

# Type check
mypy x402_bazaar/ --ignore-missing-imports
```

## License

[MIT](LICENSE)
