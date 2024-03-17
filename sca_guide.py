#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys
from typing import Final

from internal.guide import Guide
from internal.loosening import Decision, Loosening
from internal.sca import SCA

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
    parser.add_argument("--custom", "-c",
                        dest="custom",
                        required=False,
                        help="Path to the custom Wazuh SCA file to save")
    parser.add_argument("--loosening", "-l",
                        dest="loosening",
                        required=False,
                        help="Path to the list of suppression decisions from the Wazuh SCA file")

    args: argparse.Namespace = parser.parse_args()

    baseline = str(args.baseline)
    baseline = os.path.abspath(baseline)

    if (os.path.exists(baseline) is False):
        raise Exception(f"Baseline file not found at path: {baseline}")

    loosening: str = str(args.loosening)
    loosening = os.path.abspath(loosening)

    custom: str = str(args.custom)
    custom = os.path.abspath(custom)

    guide = Guide(baseline_path=baseline)

    sca: SCA = SCA.from_dict(guide.__sca_yml__)

    # Here comes the UI part
    os.system(command='cls')

    print("SCA POLICY:")
    print(f"POLICY NAME:\t\t{sca.policy.name}")
    print(f"POLICY DESCRIPTION:\t{sca.policy.description}")
    print()

    name = input("Write the name you picked for custom baseline:\n")
    id = name.lower().replace(' ', '_').replace(
        '-', '_').replace('.', '_').replace('___', '_').replace('__', '_')
    desc = input("Write a description for your custom baseline:\n")
    desc = f"{desc} (Based on {sca.policy.name})"

    l = Loosening(name=name, id=id, description=desc, decisions={})

    check_count: int = len(sca.checks)
    for i, check in enumerate(sca.checks):
        os.system(command='cls')
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

        response = input(
            "Do you want to exclude this check as an exception? [y/N] ")
        if (response == 'y' or response == 'Y'):
            justification: str = ''
            while (justification == ''):
                justification = input(
                    "Write your justification or type 'C' to cancel.\n")
                if (justification == 'c' or justification == 'C'):
                    continue
                else:
                    d = Decision(justification=justification,
                                 suppressed_check=check)
                    l.decisions[check.id] = d

    os.system('cls')
    print("Completed the customization.")

    guide.import_loosening(loosening=l)

    guide.export_loosening(loosening_path=loosening)

    guide.export_custom(custom_path=custom)

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
