"""Tests for chain configuration."""

from x402_bazaar.chains import (
    BLACKLIST_TTL,
    CHAINS,
    DEFAULT_BASE_URL,
    DEFAULT_NETWORK,
    DEFAULT_TIMEOUT,
    POLYGON_EIP712_DOMAIN,
    TRANSFER_WITH_AUTHORIZATION_TYPES,
)


def test_all_chains_present():
    assert "base" in CHAINS
    assert "base-sepolia" in CHAINS
    assert "skale" in CHAINS
    assert "polygon" in CHAINS
    assert len(CHAINS) == 4


def test_base_config():
    cfg = CHAINS["base"]
    assert cfg.chain_id == 8453
    assert cfg.usdc_contract == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert cfg.usdc_decimals == 6
    assert cfg.confirmations == 2
    assert len(cfg.rpc_urls) >= 2
    assert cfg.usdc_unit == 1_000_000


def test_skale_config():
    cfg = CHAINS["skale"]
    assert cfg.chain_id == 1187947933
    assert cfg.usdc_decimals == 18
    assert cfg.confirmations == 1
    assert cfg.usdc_unit == 10**18
    assert cfg.native_currency == "CREDITS"


def test_polygon_config():
    cfg = CHAINS["polygon"]
    assert cfg.chain_id == 137
    assert cfg.usdc_contract == "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
    assert cfg.usdc_decimals == 6
    assert cfg.native_currency == "POL"


def test_base_sepolia_config():
    cfg = CHAINS["base-sepolia"]
    assert cfg.chain_id == 84532
    assert cfg.usdc_decimals == 6
    assert cfg.confirmations == 1


def test_eip712_domain():
    assert POLYGON_EIP712_DOMAIN["name"] == "USD Coin"
    assert POLYGON_EIP712_DOMAIN["version"] == "2"
    assert POLYGON_EIP712_DOMAIN["chainId"] == 137
    assert POLYGON_EIP712_DOMAIN["verifyingContract"] == CHAINS["polygon"].usdc_contract


def test_transfer_auth_types():
    types = TRANSFER_WITH_AUTHORIZATION_TYPES["TransferWithAuthorization"]
    names = [t["name"] for t in types]
    assert names == ["from", "to", "value", "validAfter", "validBefore", "nonce"]


def test_defaults():
    assert DEFAULT_BASE_URL == "https://x402-api.onrender.com"
    assert DEFAULT_NETWORK == "skale"
    assert DEFAULT_TIMEOUT == 30
    assert BLACKLIST_TTL == 600


def test_chain_configs_frozen():
    cfg = CHAINS["base"]
    try:
        cfg.chain_id = 999  # type: ignore
        assert False, "Should be frozen"
    except AttributeError:
        pass


def test_all_chains_have_rpc_urls():
    for name, cfg in CHAINS.items():
        assert len(cfg.rpc_urls) >= 1, f"{name} has no RPC URLs"


def test_all_chains_have_explorer():
    for name, cfg in CHAINS.items():
        assert cfg.explorer.startswith("https://"), f"{name} explorer invalid"
