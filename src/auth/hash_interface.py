# defines the authentication interface for hash providers 

from __future__ import annotations #strict dictionary typing
from base64 import b64decode #for salt generation
from abc import ABC, abstractmethod #interface support
from secrets import token_bytes
from typing import NamedTuple #static typing information

#list of singleton hash provider instances
password_hash_providers: dict[str, Password_Hasher] = {}

#statically typed return
class Hash_Info(NamedTuple):
    hasher_name: str
    hash: bytes
    salt: bytes

class Password_Hasher(ABC):
    def __init__(self) -> None:
        super().__init__()
        
        name = self.provider_name
        provider = password_hash_providers.get(name)
        if provider is not None:
            self._reference_other(provider)
        else:
            password_hash_providers.update({name: self})
    
    #get the name of the provider
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    #hash a value
    @abstractmethod
    def get_hash(self, secret: bytes) -> Hash_Info:
        pass
    
    #check a password against its hash
    @abstractmethod
    def verify(self, unhashed: bytes, hashed: bytes, salt: bytes) -> bool:
        pass
    
    #generate a secure salt for passwords. Default implementation is provided
    def _generate_salt(self) -> bytes:
        return token_bytes(16)
    
    #used in case two instances of the same provider exist to ensure that all class attributes reference the same instance
    def _reference_other(self, other: Password_Hasher) -> None:
        pass