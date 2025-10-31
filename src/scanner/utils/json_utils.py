"""JSON serialization utilities for handling non-standard Python objects."""

from typing import Any


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively convert Python/JavaScript objects to JSON-serializable types.

    This function handles objects that can't be directly serialized to JSON,
    including Playwright/JavaScript objects like Error types that may appear
    in axe-core scan results.

    Args:
        obj: Any Python object to sanitize for JSON serialization

    Returns:
        A JSON-serializable version of the object

    Examples:
        >>> sanitize_for_json({"valid": "data"})
        {'valid': 'data'}

        >>> sanitize_for_json({"nested": {"error": TypeError("test")}})
        {'nested': {'error': {'error': 'test', 'type': 'TypeError'}}}
    """
    if obj is None or isinstance(obj, str | int | float | bool):
        return obj

    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}

    if isinstance(obj, list | tuple):
        return [sanitize_for_json(item) for item in obj]

    # Handle JavaScript Error objects and other non-serializable types
    if hasattr(obj, "__class__") and "Error" in obj.__class__.__name__:
        return {"error": str(obj), "type": obj.__class__.__name__}

    # Try to convert to string as fallback
    try:
        return str(obj)
    except Exception:
        return f"<non-serializable: {type(obj).__name__}>"
