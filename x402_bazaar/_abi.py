"""Minimal ERC-20 ABI fragments for USDC operations."""

# balanceOf(address) -> uint256
BALANCE_OF_SELECTOR = "0x70a08231"

# transfer(address,uint256) -> bool
TRANSFER_SELECTOR = "0xa9059cbb"

# transferWithAuthorization(address,address,uint256,uint256,uint256,bytes32,uint8,bytes32,bytes32)
TRANSFER_WITH_AUTH_SELECTOR = "0xe3ee160e"

# Full ERC-20 ABI (minimal)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]
