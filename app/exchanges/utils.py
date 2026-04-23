"""Symbol and ccxt URL helpers for Binance."""


def ccxt_binance_usdm_demo_api_urls() -> dict[str, str]:
    """USDT-M futures Demo REST roots for ccxt (`urls['api']`). Keys must be `fapi*`, not `public`/`private`."""
    base = "https://demo-fapi.binance.com"
    return {
        "fapiPublic": f"{base}/fapi/v1",
        "fapiPublicV2": f"{base}/fapi/v2",
        "fapiPublicV3": f"{base}/fapi/v3",
        "fapiPrivate": f"{base}/fapi/v1",
        "fapiPrivateV2": f"{base}/fapi/v2",
        "fapiPrivateV3": f"{base}/fapi/v3",
        "fapiData": f"{base}/futures/data",
    }


def to_ccxt_binance_futures(symbol: str) -> str:
    """Convert BTCUSDT → BTC/USDT:USDT (linear USDT-M futures)."""
    s = symbol.strip().upper()
    if "/" in s and ":" in s:
        return s
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}/USDT:USDT"
    raise ValueError(f"Unsupported symbol format: {symbol}")
