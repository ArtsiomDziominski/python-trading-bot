from decimal import Decimal

import pytest

from app.models.enums import GridDirection, VolumeMode
from app.schemas.bot import GridFuturesConfig
from app.services.risk_service import calculate_liquidation_metrics


@pytest.mark.asyncio
async def test_calculate_liquidation_metrics_long_uses_weighted_average_grid():
    config = GridFuturesConfig(
        symbol="BTCUSDT",
        direction=GridDirection.LONG,
        initial_amount=Decimal("1"),
        grid_orders_count=1,
        grid_step_percent=Decimal("10"),
        volume_mode=VolumeMode.fixed,
        start_price=Decimal("100"),
    )

    r = await calculate_liquidation_metrics(config, Decimal("10"))
    assert r.liquidation_price == Decimal("85.50")
    assert r.avg_entry_price == Decimal("95.00")
    assert r.total_base_quantity == Decimal("2")


@pytest.mark.asyncio
async def test_calculate_liquidation_metrics_short_uses_weighted_average_grid():
    config = GridFuturesConfig(
        symbol="BTCUSDT",
        direction=GridDirection.SHORT,
        initial_amount=Decimal("1"),
        grid_orders_count=1,
        grid_step_percent=Decimal("10"),
        volume_mode=VolumeMode.fixed,
        start_price=Decimal("100"),
    )

    r = await calculate_liquidation_metrics(config, Decimal("10"))
    assert r.liquidation_price == Decimal("115.50")
    assert r.avg_entry_price == Decimal("105.00")
    assert r.total_base_quantity == Decimal("2")


@pytest.mark.asyncio
async def test_calculate_liquidation_metrics_requires_anchor():
    config = GridFuturesConfig(
        symbol="BTCUSDT",
        direction=GridDirection.LONG,
        initial_amount=Decimal("1"),
        grid_orders_count=1,
        grid_step_percent=Decimal("10"),
        volume_mode=VolumeMode.fixed,
        start_price=None,
    )

    with pytest.raises(ValueError, match="Either start_price or current_price"):
        await calculate_liquidation_metrics(config, Decimal("10"))


@pytest.mark.asyncio
async def test_calculate_liquidation_metrics_rejects_when_margin_exceeds_balance():
    """Full-grid notional / leverage must not exceed total_balance (simplified)."""
    config = GridFuturesConfig(
        symbol="BTCUSDT",
        direction=GridDirection.LONG,
        initial_amount=Decimal("1"),
        grid_orders_count=1,
        grid_step_percent=Decimal("10"),
        volume_mode=VolumeMode.fixed,
        start_price=Decimal("100"),
    )
    # notional = 100*1 + 90*1 = 190; margin ≈ 190/10 = 19 > 10
    with pytest.raises(ValueError, match="total_balance"):
        await calculate_liquidation_metrics(config, Decimal("10"), total_balance=Decimal("10"))
