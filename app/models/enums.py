import enum


class ExchangeType(str, enum.Enum):
    BINANCE = "BINANCE"
    BYBIT = "BYBIT"
    OKX = "OKX"
    OTHER = "OTHER"


class UserRole(str, enum.Enum):
    USER = "USER"
    VIP = "VIP"
    SUPPORT = "SUPPORT"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"


class BotType(str, enum.Enum):
    GRID_FUTURES = "GRID_FUTURES"
    GRID_SPOT = "GRID_SPOT"
    DCA_FUTURES = "DCA_FUTURES"
    DCA_SPOT = "DCA_SPOT"
    CUSTOM = "CUSTOM"


class BotLifecycleStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"
    CLOSED = "CLOSED"


class EngineState(str, enum.Enum):
    INIT = "INIT"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    RESTARTING = "RESTARTING"
    ERROR = "ERROR"


class OrderStatus(str, enum.Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class PositionSide(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class VolumeMode(str, enum.Enum):
    linear = "linear"
    exponential = "exponential"
    fixed = "fixed"


class GridDirection(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"
