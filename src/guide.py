from typing import Final

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from loosening import Decision, Loosening

ENCODING: Final[str] = 'UTF-8'


class Guide:
    yaml: YAML
    sca_yml: CommentedMap
    loosening: Loosening

    def __init__(self, baseline_path: str) -> None:
        self.yaml = YAML()
        self.yaml.register_class(Loosening)
        self.yaml.register_class(Decision)

        with open(baseline_path, mode='r', encoding=ENCODING) as f:
            self.sca_yml = CommentedMap(self.yaml.load(f))

    def export_custom(self) -> None:
        with open(file=".tmp.new.yml", mode='w') as n:
            self.yaml.dump(self.sca_yml, n)

    def export_loosening(self) -> None:
        with open(file=".tmp.loosening.yml", mode='w') as l:
            self.yaml.dump(self.loosening, l)

    def generate_custom(self) -> None:
        self.sca_yml.get("policy")["name"] = self.loosening.name
        self.sca_yml.get("policy")["id"] = self.loosening.id
        self.sca_yml.get("policy")["description"] = self.loosening.description

        for _, id in enumerate(self.loosening.get_ids()):
            ccs: CommentedSeq = self.sca_yml.get("checks")

            for index, fi in enumerate(ccs):
                if fi.get('id') == id:
                    print(f"Removing check {id} from baseline")

                    self.sca_yml.get("checks").pop(index)

    def populate_loosening(self, selected_indices: list[int]) -> None:
        id: str = "updated_" + self.sca_yml.get("policy").get("id")
        name: str = "Custom policy"
        desc: str = "Based on " + self.sca_yml.get("policy").get("name")
        self.loosening = Loosening(
            id=id, name=name, description=desc, decisions={})
        for num in selected_indices:
            print(f"Adding check {num} to loosening list")
            checks: CommentedSeq = CommentedSeq(self.sca_yml.get("checks"))
            selected_check: CommentedMap = checks.__getsingleitem__(num)
            decision = Decision(justification="We don't want to.",
                                suppressed_check=selected_check)
            self.loosening.decisions[selected_check["id"]] = decision
