"""Tests for the Argon2id password hash provider."""

from password_hash.hash_interface import password_hash_providers
from password_hash.providers.argon2id_provider import (
    Argon2IdConfig,
    Argon2IdProvider,
    argon2id_default_provider,
)


def test_argon2id_hash_and_verify_round_trip() -> None:
    provider = Argon2IdProvider()
    password = b"password123"

    hash_info = provider.get_hash(password)

    assert hash_info.hash != password
    assert len(hash_info.salt) == 16
    assert provider.verify(password, hash_info.hash, hash_info.salt)


def test_argon2id_verify_rejects_wrong_password() -> None:
    provider = Argon2IdProvider()
    password = b"password123"

    hash_info = provider.get_hash(password)

    assert not provider.verify(b"wrong-password", hash_info.hash, hash_info.salt)


def test_duplicate_argon2id_instance_references_existing_provider() -> None:
    provider_name = argon2id_default_provider.provider_name
    registered_provider = password_hash_providers[provider_name]

    duplicate_provider = Argon2IdProvider()

    assert duplicate_provider is not registered_provider
    assert duplicate_provider.provider_name == provider_name
    assert password_hash_providers[provider_name] is registered_provider


def test_argon2id_get_config_returns_constructor_config() -> None:
    snapshot = dict(password_hash_providers)
    password_hash_providers.clear()

    try:
        expected_config = Argon2IdConfig(
            salt_len=24,
            time_cost=4,
            memory_cost=32768,
            hash_len=64,
            parallelism=2,
        )
        provider = Argon2IdProvider(config=expected_config)

        config = provider.get_config()

        assert config.salt_len == expected_config.salt_len
        assert config.time_cost == expected_config.time_cost
        assert config.memory_cost == expected_config.memory_cost
        assert config.hash_len == expected_config.hash_len
        assert config.parallelism == expected_config.parallelism
    finally:
        password_hash_providers.clear()
        password_hash_providers.update(snapshot)
