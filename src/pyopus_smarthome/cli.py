"""CLI tool to decode OPUS gateway QR codes and derive credentials."""
from __future__ import annotations

import argparse
import sys

from .auth import parse_qr_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Decode an OPUS SmartHome gateway QR code and print derived credentials.",
    )
    parser.add_argument(
        "qr_code",
        help="QR code string, e.g. 30S0000AABBCCDD+1P00400000002B+S12345678",
    )
    args = parser.parse_args()

    try:
        creds = parse_qr_code(args.qr_code)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"EURID:           {creds.eurid}")
    print(f"Product ID:      {creds.product_id}")
    print(f"Serial:          {creds.serial}")
    print()
    print(f"Port 8080 auth:  admin:{creds.admin_password}")
    print(f"Port 8099 auth:  ConfigUser:{creds.config_password}")
    print(f"Port 80 auth:    AlexaConfigUser:{creds.serial}")


if __name__ == "__main__":
    main()
