#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import random
import sys
from typing import Final


from guide import Guide
from sca import SCA

APP_NAME: Final[str] = 'scaGuide'
APP_VERSION: Final[str] = '0.1'
ENCODING: Final[str] = 'UTF-8'


def debug(msg: str) -> None:
    print(msg)
    logging.debug(msg)


def get_selected(check_count) -> list[int]:
    selected_indices: list[int] = [x for x
                                   in random.choices(range(0, check_count), k=10)]
    selected_indices.sort()
    return selected_indices


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=f"{APP_NAME} ({APP_VERSION}) is a demo application.")
    if (len(sys.argv)) == 1:
        parser.print_help()

    parser.add_argument("--baseline", "-b",
                        dest="baseline",
                        required=False,
                        help="Path to the Wazuh SCA file to start with")
    args: argparse.Namespace = parser.parse_args()

    baseline = str(args.baseline)

    baseline = os.path.abspath(baseline)

    if (os.path.exists(baseline) is False):
        raise Exception(f"Baseline file not found at path: {baseline}")

    guide = Guide(baseline_path=baseline)

    sca: SCA = SCA.from_dict(guide.sca_yml)

    print("SCA POLICY:")
    print(f"POLICY NAME:\t\t{sca.policy.name}")
    print(f"POLICY DESCRIPTION:\t{sca.policy.description}")
    print()

    check_count: int = len(sca.checks)
    for i, check in enumerate(sca.checks):
        print(
            f"CHECK ID:\t#{check.id} ({i+1} of {check_count}):")
        print(
            f"TITLE:\t\t{check.title}")
        print(
            f"DESCRIPTION:\t{check.description}")
        if check.rationale:
            print(f"RATIONALE:\t{check.rationale}")
        if check.remediation:
            print(f"REMEDIATION:\t{check.remediation}")
        print()

    selected_indices: list[int] = get_selected(check_count=check_count)

    # Complexity O(n)
    guide.populate_loosening(selected_indices=selected_indices)

    # Remove from original
    # Complexity O(m*n) or O(n^2)
    guide.generate_custom()

    guide.export_loosening()

    guide.export_custom()

    debug("Exiting")


def get_root_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    elif __file__:
        return os.path.dirname(__file__)
    else:
        return './'


if __name__ == "__main__":
    try:
        logging.basicConfig(filename=os.path.join(get_root_dir(), f'{APP_NAME}.log'),
                            encoding=ENCODING,
                            format='%(asctime)s:%(levelname)s:%(message)s',
                            datefmt="%Y-%m-%dT%H:%M:%S%z",
                            level=logging.INFO)

        excepthook = logging.error
        logging.info('Starting')
        main()
        logging.info('Exiting.')
    except KeyboardInterrupt:
        logging.warning('Cancelled by user.')
        logging.info('Exiting.')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as ex:
        logging.error('ERROR: ' + str(ex))
        logging.info('Exiting.')
        try:
            sys.exit(1)
        except SystemExit:
            os._exit(1)
