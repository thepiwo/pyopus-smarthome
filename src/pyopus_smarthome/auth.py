from __future__ import annotations
from dataclasses import dataclass


def derive_admin_password(eurid: str) -> str:
    """Derive port 8080 admin password from EURID (last 8 hex chars)."""
    return eurid[-8:].upper()


def derive_config_password(eurid: str, serial: str) -> str:
    """Derive port 8099 ConfigUser password from EURID + serial."""
    return f"{eurid[-8:].upper()}-{serial}"


@dataclass
class QRCredentials:
    """Credentials derived from an OPUS gateway QR code."""

    eurid: str
    product_id: str
    serial: str

    @property
    def admin_password(self) -> str:
        return derive_admin_password(self.eurid)

    @property
    def config_password(self) -> str:
        return derive_config_password(self.eurid, self.serial)


def parse_qr_code(qr: str) -> QRCredentials:
    """Parse an OPUS gateway QR code and derive all credentials.

    QR format: ``30S<EURID>+1P<PRODUCT_ID>+S<SERIAL>``

    Example::

        creds = parse_qr_code("30S0000AABBCCDD+1P00400000002B+S12345678")
        creds.eurid          # "0000AABBCCDD"
        creds.admin_password # "AABBCCDD"
        creds.config_password # "AABBCCDD-12345678"
    """
    parts = qr.split("+")
    if len(parts) != 3:
        raise ValueError(f"Expected 3 QR segments separated by '+', got {len(parts)}")

    eurid_part, product_part, serial_part = parts

    if not eurid_part.startswith("30S"):
        raise ValueError(f"First segment must start with '30S', got '{eurid_part[:3]}'")
    if not product_part.startswith("1P"):
        raise ValueError(f"Second segment must start with '1P', got '{product_part[:2]}'")
    if not serial_part.startswith("S"):
        raise ValueError(f"Third segment must start with 'S', got '{serial_part[:1]}'")

    return QRCredentials(
        eurid=eurid_part[3:],
        product_id=product_part[2:],
        serial=serial_part[1:],
    )
