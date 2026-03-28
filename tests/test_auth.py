import pytest
from pyopus_smarthome.auth import (
    derive_admin_password,
    derive_config_password,
    parse_qr_code,
    QRCredentials,
)


def test_derive_admin_password_from_eurid():
    assert derive_admin_password("AABBCCDD") == "AABBCCDD"


def test_derive_admin_password_from_long_eurid():
    # If EURID is longer, take last 8
    assert derive_admin_password("0000AABBCCDD") == "AABBCCDD"


def test_derive_config_password():
    assert derive_config_password("AABBCCDD", "12345678") == "AABBCCDD-12345678"


# --- QR code parsing ---


def test_parse_qr_code():
    creds = parse_qr_code("30S0000AABBCCDD+1P00400000002B+S12345678")
    assert creds.eurid == "0000AABBCCDD"
    assert creds.product_id == "00400000002B"
    assert creds.serial == "12345678"


def test_parse_qr_code_admin_password():
    creds = parse_qr_code("30S0000AABBCCDD+1P00400000002B+S12345678")
    assert creds.admin_password == "AABBCCDD"


def test_parse_qr_code_config_password():
    creds = parse_qr_code("30S0000AABBCCDD+1P00400000002B+S12345678")
    assert creds.config_password == "AABBCCDD-12345678"


def test_parse_qr_code_invalid_format():
    with pytest.raises(ValueError, match="3 QR segments"):
        parse_qr_code("invalid")


def test_parse_qr_code_bad_prefix():
    with pytest.raises(ValueError, match="must start with '30S'"):
        parse_qr_code("XXS0000AABBCCDD+1P00400000002B+S12345678")
