"""Trusted Python SQLite primitives; domain repositories own semantic validation."""
from .store import StorageError, Store, database_path

__all__ = ['StorageError', 'Store', 'database_path']
