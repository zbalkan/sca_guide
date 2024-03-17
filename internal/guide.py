import os
from typing import Final

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from internal.loosening import Decision, Loosening
from internal.sca import Check, Compliance

ENCODING: Final[str] = 'UTF-8'


class Guide:
    __yaml__: YAML
    __sca_yml__: CommentedMap
    __loosening__: Loosening

    def __init__(self, baseline_path: str) -> None:
        self.__yaml__ = YAML()
        self.__yaml__.register_class(Loosening)
        self.__yaml__.register_class(Decision)
        self.__yaml__.register_class(Check)
        self.__yaml__.register_class(Compliance)

        with open(baseline_path, mode='r', encoding=ENCODING) as fs:
            self.__sca_yml__ = CommentedMap(self.__yaml__.load(fs))

    def import_loosening(self, loosening: Loosening) -> None:
        self.__loosening__ = loosening

    def export_custom(self, custom_path: str) -> None:
        custom = CommentedMap(self.__sca_yml__.copy())
        custom.get("policy")[
            "name"] = self.__loosening__.name + " Loosening Guide"
        custom.get("policy")["id"] = self.__loosening__.id + "_loosening"
        custom.get("policy")[
            "description"] = self.__loosening__.description
        custom.get("policy")["file"] = os.path.basename(custom_path)

        for _, id in enumerate(self.__loosening__.get_ids()):
            ccs: CommentedSeq = custom.get("checks")

            for index, fi in enumerate(ccs):
                if fi.get('id') == id:
                    print(f"Removing check {id} from baseline")

                    custom.get("checks").pop(index)

        with open(file=custom_path, mode='w') as fs:
            self.__yaml__.dump(self.__sca_yml__, fs)

    def export_loosening(self, loosening_path: str) -> None:
        with open(file=loosening_path, mode='w') as fs:
            self.__yaml__.dump(self.__loosening__, fs)
