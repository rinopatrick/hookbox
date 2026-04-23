"""Custom exception hierarchy for Hookbox."""

from __future__ import annotations


class HookboxError(Exception):
    """Base exception for the Hookbox application."""


class NotFoundError(HookboxError):
    """Raised when a requested resource is not found."""


class ValidationError(HookboxError):
    """Raised when input validation fails."""


class StorageError(HookboxError):
    """Raised when a database operation fails."""
