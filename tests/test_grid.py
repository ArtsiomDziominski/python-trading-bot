from decimal import Decimal

from app.models.enums import GridDirection, VolumeMode
from app.strategies.grid import (
    GridLevelKind,
    client_order_id,
    close_position_order_id,
    grid_prices,
    level_size,
)


def test_client_order_id_format():
    cid = client_order_id(1, 2, GridLevelKind.entry, 0)
    assert cid.startswith("b1-v2")


def test_close_order_id():
    assert "close" in close_position_order_id(1, 3)


def test_level_size_modes():
    assert level_size(Decimal("1"), 0, VolumeMode.fixed) == Decimal("1")
    assert level_size(Decimal("1"), 0, VolumeMode.linear) == Decimal("1")
    assert level_size(Decimal("1"), 1, VolumeMode.linear) == Decimal("2")
    assert level_size(Decimal("2"), 1, VolumeMode.exponential) == Decimal("4")


def test_grid_prices_long():
    prices = grid_prices(
        Decimal("100"),
        direction=GridDirection.LONG,
        grid_orders_count=3,
        grid_step_percent=Decimal("1"),
    )
    assert len(prices) == 3
    assert prices[0] < Decimal("100")
