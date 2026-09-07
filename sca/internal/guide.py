import hashlib
import html
import os
from copy import deepcopy

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from sca.config import VERSION
from sca.internal.loosening import Tailoring
from sca.internal.review import DecisionType
from sca.internal.sca import Compliance, SCA

ENCODING = 'UTF-8'


def escape_markdown(value: object) -> str:
    text = html.escape(str(value), quote=False).replace('\\', '\\\\')
    for character in '[]()#->*_`':
        text = text.replace(character, f'\\{character}')
    return text


def escape_markdown_cell(value: object) -> str:
    return (escape_markdown(value).replace('|', '\\|')
            .replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>'))


def _sha256(path: str) -> str:
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def _compliance_text(compliance: list[Compliance] | None) -> str:
    values: list[str] = []
    for mapping in compliance or []:
        for framework, identifiers in mapping.items():
            values.append(f"{framework}: {', '.join(str(value) for value in identifiers)}")
    return '; '.join(values) if values else '—'


class Guide:
    def __init__(self, baseline_path: str) -> None:
        self.baseline_path = baseline_path
        self.__yaml__ = YAML()
        with open(baseline_path, mode='r', encoding=ENCODING) as stream:
            self.__sca_yml__ = CommentedMap(self.__yaml__.load(stream))
        self.sca = SCA.from_dict(self.__sca_yml__)

    def export_custom(self, tailoring: Tailoring, custom_path: str) -> None:
        custom = deepcopy(self.__sca_yml__)
        policy = custom['policy']
        policy['name'] = tailoring.name
        policy['id'] = tailoring.id
        policy['description'] = tailoring.description
        policy['file'] = os.path.basename(custom_path)
        custom['checks'][:] = [
            check for check in custom['checks']
            if check.get('id') not in tailoring.decisions
        ]
        with open(custom_path, mode='w', encoding=ENCODING) as stream:
            self.__yaml__.dump(custom, stream)

    def export_exceptions(self, tailoring: Tailoring, tailored_path: str,
                          yml_path: str, md_path: str, generated_at: str) -> None:
        sca = self.sca
        baseline_digest = _sha256(self.baseline_path)
        tailored_digest = _sha256(tailored_path)

        removed = sorted(tailoring.decisions.items())

        def record_items(kind: DecisionType) -> list[dict[str, object]]:
            return [
                {
                    'check_id': check_id,
                    'title': removal.check.title,
                    'justification': removal.justification,
                    'compliance': [dict(item) for item in removal.check.compliance]
                    if removal.check.compliance else [],
                }
                for check_id, removal in removed
                if removal.decision is kind
            ]

        record = {
            'baseline': {
                'name': sca.policy.name,
                'id': sca.policy.id,
                'file': sca.policy.file,
                'sha256': baseline_digest,
            },
            'tailored_policy': {
                'name': tailoring.name,
                'id': tailoring.id,
                'file': os.path.basename(tailored_path),
                'sha256': tailored_digest,
            },
            'generated_by': {'tool': 'wazuhscatune', 'version': VERSION},
            'generated_at': generated_at,
            'exceptions': {
                'accepted_risk': record_items(DecisionType.EXCEPTION),
                'not_applicable': record_items(DecisionType.NOT_APPLICABLE),
            },
        }

        with open(yml_path, mode='w', encoding=ENCODING) as stream:
            self.__yaml__.dump(record, stream)

        with open(md_path, mode='w', encoding=ENCODING) as stream:
            stream.write(f"# {escape_markdown(tailoring.name)} Exception Record\n\n")
            stream.write(
                f"## {escape_markdown(tailoring.name)} "
                f"({escape_markdown(tailoring.id)})\n\n"
            )
            stream.write(f"{escape_markdown(tailoring.description)}\n\n")
            stream.write(
                f"Baseline: {escape_markdown(sca.policy.name)} "
                f"(`{escape_markdown(sca.policy.id)}`)  \n"
                f"SHA-256: `{baseline_digest}`\n\n"
            )

            sections = (
                ('Accepted Risk Exceptions', DecisionType.EXCEPTION),
                ('Not Applicable', DecisionType.NOT_APPLICABLE),
            )
            for heading, kind in sections:
                stream.write(f"## {heading}\n\n")
                stream.write("| Check ID | Check Name | Compliance | Justification |\n")
                stream.write("| --- | --- | --- | --- |\n")
                for check_id, removal in removed:
                    if removal.decision is not kind:
                        continue
                    stream.write(
                        f"| {check_id} | {escape_markdown_cell(removal.check.title)} | "
                        f"{escape_markdown_cell(_compliance_text(removal.check.compliance))} | "
                        f"{escape_markdown_cell(removal.justification)} |\n"
                    )
                stream.write("\n")

            stream.write(
                "## Notes\n\nGenerated by `wazuhscatune`. "
                "Update the exception record and tailored policy together.\n"
            )
