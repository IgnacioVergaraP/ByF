"""Utilidades de seguridad (placeholder para futuras subetapas)."""


def validate_upload_size(size_bytes: int, max_mb: int = 20) -> bool:
    return size_bytes <= max_mb * 1024 * 1024