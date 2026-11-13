#!/usr/bin/env python3
"""Print a salted scrypt hash for one employee time-sheet PIN.

The PIN is not stored. Paste the printed hash into Streamlit secrets under
[timesheet_pins], using the employee's exact time-sheet name as the key.
Do not commit the PIN or the hash.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import timesheet_pin


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a [timesheet_pins] hash. The PIN is not saved."
    )
    parser.add_argument(
        "--employee",
        help="Exact employee name. When set, the output is a secrets.toml line.",
    )
    parser.add_argument(
        "--pin",
        help="PIN text. Omit this and type the PIN at the prompt so it is not stored in shell history.",
    )
    args = parser.parse_args(argv)
    if args.employee is not None and not timesheet_pin.employee_allowed(args.employee):
        names = ", ".join(timesheet_pin.PIN_EMPLOYEES)
        print("Unknown employee. Use one of: " + names, file=sys.stderr)
        return 2
    if args.pin is not None:
        print(
            "Warning: --pin can be saved in shell history. Prefer the prompt.",
            file=sys.stderr,
        )
        pin = args.pin
        confirm = args.pin
    else:
        pin = getpass.getpass("PIN: ")
        confirm = getpass.getpass("PIN again: ")
    if pin != confirm:
        print("PINs did not match.", file=sys.stderr)
        return 2
    try:
        hashed = timesheet_pin.make_pin_hash(pin)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.employee:
        print('"%s" = "%s"' % (args.employee, hashed))
    else:
        print(hashed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
