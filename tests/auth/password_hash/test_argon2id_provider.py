"""Tests for the Argon2id password hash provider."""

from password_hash.hash_interface import password_hash_providers
from password_hash.providers.argon2id_provider import argon2id, argon2id_default_provider


def test_argon2id_hash_and_verify_round_trip() -> None:
    provider = argon2id()
    password = b"password123"

    hash_info = provider.get_hash(password)

    assert hash_info.hash != password
    assert len(hash_info.salt) == 16
    assert provider.verify(password, hash_info.hash, hash_info.salt)


def test_argon2id_verify_rejects_wrong_password() -> None:
    provider = argon2id()
    password = b"password123"

    hash_info = provider.get_hash(password)

    assert not provider.verify(b"wrong-password", hash_info.hash, hash_info.salt)


def test_duplicate_argon2id_instance_references_existing_provider() -> None:
    provider_name = argon2id_default_provider.provider_name
    registered_provider = password_hash_providers[provider_name]

    duplicate_provider = argon2id()

    assert duplicate_provider is not registered_provider
    assert duplicate_provider.provider_name == provider_name
    assert password_hash_providers[provider_name] is registered_provider
