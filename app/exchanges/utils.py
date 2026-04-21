"""Symbol helpers for ccxt unified symbols."""


def to_ccxt_binance_futures(symbol: str) -> str:
    """Convert BTCUSDT → BTC/USDT:USDT (linear USDT-M futures)."""
    s = symbol.strip().upper()
    if "/" in s and ":" in s:
        return s
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}/USDT:USDT"
    raise ValueError(f"Unsupported symbol format: {symbol}")
