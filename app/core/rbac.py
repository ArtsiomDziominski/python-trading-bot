from app.core.config import get_settings
from app.models.enums import UserRole


def max_api_keys_for_role(role: UserRole) -> int:
    s = get_settings()
    match role:
        case UserRole.USER:
            return s.max_api_keys_user
        case UserRole.VIP:
            return s.max_api_keys_vip
        case UserRole.SUPPORT:
            return s.max_api_keys_support
        case UserRole.ADMIN:
            return s.max_api_keys_admin
        case UserRole.SUPERADMIN:
            return s.max_api_keys_superadmin
    return s.max_api_keys_user


def max_active_bots_for_role(role: UserRole) -> int:
    s = get_settings()
    match role:
        case UserRole.USER:
            return s.max_active_bots_user
        case UserRole.VIP:
            return s.max_active_bots_vip
        case UserRole.SUPPORT:
            return s.max_active_bots_support
        case UserRole.ADMIN:
            return s.max_active_bots_admin
        case UserRole.SUPERADMIN:
            return s.max_active_bots_superadmin
    return s.max_active_bots_user


def role_at_least(user_role: UserRole, minimum: UserRole) -> bool:
    order = [
        UserRole.USER,
        UserRole.VIP,
        UserRole.SUPPORT,
        UserRole.ADMIN,
        UserRole.SUPERADMIN,
    ]
    return order.index(user_role) >= order.index(minimum)
