# Changelog

## [1.3.0] - 2026-04-02

### Added
- Parallel balance queries: `get_balance()` uses ThreadPoolExecutor, `get_balance_async()` uses asyncio.gather()
- Async CrewAI support: `_arun()` method on all CrewAI tools
- Enriched LangChain tool descriptions for better LLM orchestration
- Convenience imports in `integrations/__init__.py` with `__all__`

### Improved
- 147 tests (was 103)

## [1.2.1] - 2026-04-01

### Fixed
- All ruff and mypy lint errors resolved (clean CI)

## [1.2.0] - 2026-03-31

### Added
- HMAC-SHA256 response signature verification (`validation_secret` parameter)
- Quality score check: auto-blacklist services returning empty/invalid data
- `fund_wallet()` method with per-chain funding instructions
- `claim_faucet_async()` method for async SKALE faucet claims
- GitHub Actions CI (Python 3.10-3.13, unit + integration tests)
- LICENSE file (MIT)
- CHANGELOG.md
- 11 async tests covering all async methods
- 9 live integration tests against real backend
- 22 validation tests (HMAC, quality score, fund_wallet)

### Fixed
- Repository URL in pyproject.toml (was pointing to wrong org)

## [1.1.0] - 2026-03-31

### Added
- HMAC validation, quality score check, fund_wallet (pre-release, same day)

## [1.0.0] - 2026-03-31

### Added
- `X402Client` with auto-payment (HTTP 402 detection, USDC payment, retry)
- Multi-chain support: Base, Polygon (EIP-3009 gas-free), SKALE, Base Sepolia
- Wallet management: generate, import, encrypt/decrypt AES-256-GCM
- Budget tracking: daily/weekly/monthly spending limits with auto-reset
- Lightweight JSON-RPC client (no web3.py dependency)
- LangChain integration: `X402SearchTool` + `X402CallTool`
- CrewAI integration: `X402SearchTool` + `X402CallTool`
- 12 Pydantic models, 8 typed exception classes
- Full type hints with `py.typed` marker (PEP 561)
- 103 unit tests
