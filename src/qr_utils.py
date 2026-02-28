"""
Utility functions for QR code generation for Pyrogram QR login.
These are pure functions with no Telegram API calls, making them fully testable.
"""

import base64


def generate_qr_link(token: bytes) -> str:
    """
    Convert a raw login token (bytes) to a tg://login deeplink URL.

    Args:
        token: Raw token bytes from Telegram's ExportLoginToken response.

    Returns:
        A string like 'tg://login?token=<base64url-encoded-token>'.
    """
    encoded = base64.urlsafe_b64encode(token).decode("utf-8").rstrip("=")
    return f"tg://login?token={encoded}"


def generate_qr_image(link: str, filename: str = "login_qr.png") -> None:
    """
    Generate a QR code PNG image from a tg://login link.

    Requires the 'qrcode[pil]' package. The caller is responsible for
    ensuring the package is installed before calling this function.

    Args:
        link: A tg://login deeplink URL (result of generate_qr_link).
        filename: Output filename for the PNG image.
    """
    import qrcode  # type: ignore[import]

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
