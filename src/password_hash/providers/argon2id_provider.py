"""Argon2id password hash provider."""

from dataclasses import dataclass
from secrets import token_bytes

from argon2 import low_level
from argon2.low_level import Type

from ..hash_interface import AbstractPasswordHasher, HashInfo


@dataclass(frozen=True)
class Argon2IdConfig:
    salt_len: int = 16
    time_cost: int = 3
    memory_cost: int = 65536
    hash_len: int = 32
    parallelism: int = 4


class Argon2IdProvider(AbstractPasswordHasher):
    default_salt: bytes = "usedforcookies".encode()
    
    def __init__(self, config: Argon2IdConfig | None = None) -> None:
        self._config = config or Argon2IdConfig()
        self._version = 19

        super().__init__()

    def get_hash(self, secret: bytes) -> HashInfo:
        salt = self._generate_salt()
        return self.get_hash_with_salt(secret, salt)

    def get_hash_with_salt(self, secret: bytes, salt: bytes) -> HashInfo:
        if len(salt) == 0:
            salt = self.default_salt
        hash_result = low_level.hash_secret_raw(
            secret,
            salt,
            self._config.time_cost,
            self._config.memory_cost,
            self._config.parallelism,
            self._config.hash_len,
            Type.ID,
            self._version,
        )
        return HashInfo(self.provider_name, hash_result, salt)

    def verify(self, unhashed: bytes, hashed: bytes, salt: bytes) -> bool:
        expected_hash = low_level.hash_secret_raw(
            unhashed,
            salt,
            self._config.time_cost,
            self._config.memory_cost,
            self._config.parallelism,
            self._config.hash_len,
            Type.ID,
            self._version,
        )
        return expected_hash == hashed

    def verify_no_salt(self, unhashed: bytes, hashed: bytes) -> bool:
        expected_hash = low_level.hash_secret_raw(
            unhashed,
            self.default_salt,
            self._config.time_cost,
            self._config.memory_cost,
            self._config.parallelism,
            self._config.hash_len,
            Type.ID,
            self._version,
        )
        return expected_hash == hashed

    def _generate_salt(self) -> bytes:
        return token_bytes(self._config.salt_len)

    def _reference_other(self, other: AbstractPasswordHasher) -> None:
        if isinstance(other, Argon2IdProvider):
            self._config = other.get_config()
        else:
            raise RuntimeError(
                "hashing provider tried to reference a different provider subclass"
            )

    def get_config(self) -> Argon2IdConfig:
        return self._config

    @property
    def provider_name(self) -> str:
        return (
            f"argon2id$v:{self._version}$s:{self._config.salt_len}$h:{self._config.hash_len}"
            f"$m:{self._config.memory_cost}$t:{self._config.time_cost}$p{self._config.parallelism}"
        )


argon2id_default_provider = Argon2IdProvider()


if __name__ == "__main__":
    def to_hex(value: bytes) -> str:
        hex_string = " ".join(f"{b:0X}" for b in value)
        return hex_string

    PASSWORD = "password123"

    print(
        "Hashing password using argon2id: "
        f"plaintext: {PASSWORD}, encoded: {to_hex(PASSWORD.encode())}"
    )
    hash_info: HashInfo = argon2id_default_provider.get_hash(PASSWORD.encode())

    print(f"algorithm name: {hash_info.hasher_name}")
    print(f"hash: {to_hex(hash_info.hash)}, salt: {to_hex(hash_info.salt)}")

    print("verifying hash... ", end="")
    print(
        argon2id_default_provider.verify(
            PASSWORD.encode(), hash_info.hash, hash_info.salt
        )
    )
