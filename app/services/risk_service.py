from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.models.enums import GridDirection
from app.schemas.bot import GridFuturesConfig
from app.strategies.grid import grid_prices, level_size


@dataclass(frozen=True, slots=True)
class LiquidationCalculationResult:
    liquidation_price: Decimal
    avg_entry_price: Decimal
    total_base_quantity: Decimal


async def calculate_liquidation_metrics(
    config: GridFuturesConfig,
    leverage: Decimal,
    *,
    total_balance: Optional[Decimal] = None,
    current_price: Optional[Decimal] = None,
) -> LiquidationCalculationResult:
    """
    Grid liquidation with balance-aware model (cross-like).

    - Учитывает total_balance
    - Чем больше баланс → тем дальше ликвидация
    """

    if leverage <= 0:
        raise ValueError("leverage must be greater than 0")

    base_price = config.start_price or current_price
    if base_price is None:
        raise ValueError("Either start_price or current_price must be provided")

    # 🔹 Сетка цен
    grid_levels = grid_prices(
        base_price,
        direction=config.direction,
        grid_orders_count=config.grid_orders_count,
        grid_step_percent=config.grid_step_percent,
    )

    prices = [base_price, *grid_levels]

    # 🔹 Объёмы
    quantities = [
        config.initial_amount,
        *[
            level_size(config.initial_amount, index, config.volume_mode)
            for index in range(config.grid_orders_count)
        ],
    ]

    # 🔹 Номинал позиции
    notional_usdt = sum(
        price * quantity for price, quantity in zip(prices, quantities, strict=True)
    )

    # 🔹 Общий объём
    total_base_quantity = sum(quantities, Decimal("0"))
    if total_base_quantity == 0:
        raise ValueError("Total quantity is zero")

    # 🔹 Средняя цена
    avg_entry_price = notional_usdt / total_base_quantity

    # 🔥 🔥 🔥 НОВАЯ ЛОГИКА ЛИКВИДАЦИИ 🔥 🔥 🔥

    if total_balance is None or total_balance <= 0:
        raise ValueError("total_balance must be provided for balance-aware calculation")

    # эффективное плечо (чем больше баланс — тем меньше риск)
    effective_leverage = notional_usdt / total_balance

    # защита от деления на 0 / слишком маленького плеча
    if effective_leverage <= 1:
        # почти без плеча → ликвидация очень далеко
        effective_leverage = Decimal("1.01")

    if config.direction == GridDirection.LONG:
        liquidation_price = avg_entry_price * (
            Decimal("1") - (Decimal("1") / effective_leverage)
        )
    else:
        liquidation_price = avg_entry_price * (
            Decimal("1") + (Decimal("1") / effective_leverage)
        )

    # 🔹 Проверка сетки
    if grid_levels:
        if config.direction == GridDirection.LONG:
            lowest_price = min(grid_levels)

            if liquidation_price >= lowest_price:
                raise ValueError(
                    f"Unsafe grid: liquidation ({liquidation_price:.2f}) "
                    f"is inside grid range (lowest: {lowest_price:.2f})"
                )
        else:
            highest_price = max(grid_levels)

            if liquidation_price <= highest_price:
                raise ValueError(
                    f"Unsafe grid: liquidation ({liquidation_price:.2f}) "
                    f"is inside grid range (highest: {highest_price:.2f})"
                )

    # 🔹 Округление
    q = Decimal("0.01")

    return LiquidationCalculationResult(
        liquidation_price=liquidation_price.quantize(q),
        avg_entry_price=avg_entry_price.quantize(q),
        total_base_quantity=total_base_quantity,
    )