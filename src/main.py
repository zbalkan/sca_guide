#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys
from typing import Final

from ruamel.yaml import YAML

from sca import SCA

APP_NAME: Final[str] = 'scaGuide'
APP_VERSION: Final[str] = '0.1'
ENCODING: Final[str] = 'UTF-8'


def debug(msg: str) -> None:
    print(msg)
    logging.debug(msg)


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

    with open(baseline, mode='r', encoding=ENCODING) as f:
        yaml = YAML(typ='safe')
        yml = yaml.load(f)
        if yml:
            s = SCA.from_dict(yml)

            print("SCA POLICY:")
            print(f"POLICY NAME:\t\t{s.policy.name}")
            print(f"POLICY DESCRIPTION:\t{s.policy.description}")
            print()

            check_count = len(s.checks)
            for i, check in enumerate(s.checks):
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
