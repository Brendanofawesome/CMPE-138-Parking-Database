"""Tests for provider registration in the hash interface registry."""

import importlib

from password_hash.hash_interface import password_hash_providers


def test_imported_provider_registers_in_password_hash_providers() -> None:
    snapshot = dict(password_hash_providers)
    password_hash_providers.clear()

    try:
        provider_module = importlib.import_module("password_hash.providers.argon2id_provider")
        provider_module = importlib.reload(provider_module)

        provider = provider_module.argon2id_default_provider
        assert provider.provider_name in password_hash_providers
        assert password_hash_providers[provider.provider_name] is provider
    finally:
        password_hash_providers.clear()
        password_hash_providers.update(snapshot)
