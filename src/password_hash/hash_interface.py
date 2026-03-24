"""Authentication interfaces for password hash providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from secrets import token_bytes
from typing import NamedTuple

# Singleton hash provider instances keyed by provider name.
password_hash_providers: dict[str, "Abstract_Password_Hasher"] = {}


class Hash_Info(NamedTuple):
    hasher_name: str
    hash: bytes
    salt: bytes


class Abstract_Password_Hasher(ABC):
    def __init__(self) -> None:
        super().__init__()

        name = self.provider_name
        provider = password_hash_providers.get(name)
        if provider is not None:
            self._reference_other(provider)
        else:
            password_hash_providers[name] = self

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return a unique provider name and configuration signature."""

    @abstractmethod
    def get_hash(self, secret: bytes) -> Hash_Info:
        """Generate a hash and salt for the provided secret."""

    @abstractmethod
    def verify(self, unhashed: bytes, hashed: bytes, salt: bytes) -> bool:
        """Verify unhashed bytes against a known hash and salt."""

    def _generate_salt(self) -> bytes:
        return token_bytes(16)

    def _reference_other(self, other: "Abstract_Password_Hasher") -> None:
        """Copy state from an existing singleton provider when needed."""
