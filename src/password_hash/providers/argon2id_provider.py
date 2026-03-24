"""Argon2id password hash provider."""

from argon2 import low_level
from argon2.low_level import Type
from secrets import token_bytes

from ..hash_interface import Hash_Info, Abstract_Password_Hasher


class argon2id(Abstract_Password_Hasher):
    def __init__(
        self,
        salt_len: int = 16,
        time_cost: int = 3,
        memory_cost: int = 65536,
        hash_len: int = 32,
        parallelism: int = 4,
    ) -> None:
        self._salt_len = salt_len
        self._hash_len = hash_len
        self._time_cost = time_cost
        self._parallelism = parallelism
        self._memory_cost = memory_cost
        self._version = 19

        super().__init__()

    def get_hash(self, secret: bytes) -> Hash_Info:
        salt = self._generate_salt()
        hash_result = low_level.hash_secret_raw(
            secret,
            salt,
            self._time_cost,
            self._memory_cost,
            self._parallelism,
            self._hash_len,
            Type.ID,
            self._version,
        )
        return Hash_Info(self.provider_name, hash_result, salt)

    def verify(self, unhashed: bytes, hashed: bytes, salt: bytes) -> bool:
        expected_hash = low_level.hash_secret_raw(
            unhashed,
            salt,
            self._time_cost,
            self._memory_cost,
            self._parallelism,
            self._hash_len,
            Type.ID,
            self._version,
        )
        return expected_hash == hashed

    def _generate_salt(self) -> bytes:
        return token_bytes(self._salt_len)

    def _reference_other(self, other: Abstract_Password_Hasher) -> None:
        if isinstance(other, argon2id):
            self._salt_len = other._salt_len
            self._hash_len = other._hash_len
            self._time_cost = other._time_cost
            self._parallelism = other._parallelism
            self._memory_cost = other._memory_cost
        else:
            raise RuntimeError(
                "hashing provider tried to reference a different provider subclass"
            )

    @property
    def provider_name(self) -> str:
        return (
            f"argon2id$v:{self._version}$s:{self._salt_len}$h:{self._hash_len}"
            f"$m:{self._memory_cost}$t:{self._time_cost}$p{self._parallelism}"
        )


argon2id_default_provider = argon2id()


if __name__ == "__main__":
    def to_hex(input: bytes) -> str:
        hex_string = ' '.join(f'{b:0X}' for b in input)
        return hex_string
    
    password: str = "password123"

    print(
        f"Hashing password using argon2id: plaintext: {password}, encoded: {to_hex(password.encode())}"
    )
    hash_info: Hash_Info = argon2id_default_provider.get_hash(password.encode())

    print(f"algorithm name: {hash_info.hasher_name}")
    print(f"hash: {to_hex(hash_info.hash)}, salt: {to_hex(hash_info.salt)}")

    print("verifying hash... ", end="")
    print(argon2id_default_provider.verify(password.encode(), hash_info.hash, hash_info.salt))
