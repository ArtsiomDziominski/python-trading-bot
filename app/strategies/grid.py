"""Grid futures: deterministic client_order_id and per-level sizes."""

from decimal import Decimal
from enum import Enum

from app.models.enums import GridDirection, VolumeMode


class GridLevelKind(str, Enum):
    entry = "entry"
    grid = "grid"


def client_order_id(bot_id: int, config_version: int, kind: GridLevelKind, index: int) -> str:
    raw = f"b{bot_id}-v{config_version}-{kind.value}-{index}"
    return raw[:128]


def close_position_order_id(bot_id: int, config_version: int) -> str:
    """Идемпотентный id для market reduce-only при закрытии бота."""
    raw = f"b{bot_id}-v{config_version}-close"
    return raw[:128]


def level_size(initial: Decimal, index: int, mode: VolumeMode) -> Decimal:
    """index 0 = first grid leg after entry."""
    if mode == VolumeMode.fixed:
        return initial
    if mode == VolumeMode.linear:
        return initial * Decimal(index + 1)
    if mode == VolumeMode.exponential:
        return initial * (Decimal(2) ** index)
    return initial


def grid_prices(
    start_price: Decimal,
    *,
    direction: GridDirection,
    grid_orders_count: int,
    grid_step_percent: Decimal,
) -> list[Decimal]:
    """Limit prices for grid legs (not including optional market entry)."""
    out: list[Decimal] = []
    step = grid_step_percent / Decimal("100")
    p = start_price
    for _ in range(grid_orders_count):
        if direction == GridDirection.LONG:
            p = p * (Decimal("1") - step)
        else:
            p = p * (Decimal("1") + step)
        out.append(p)
    return out
