"""Auth utilities - re-exports from deps for backward compatibility."""

from .deps import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    get_current_user,
    require_admin,
)

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "get_current_user",
    "require_admin",
]
