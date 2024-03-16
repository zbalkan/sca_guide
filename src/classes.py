'''
Reference:
https://documentation.wazuh.com/current/user-manual/capabilities/sec-config-assessment/creating-custom-policies.html
'''

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Compliance:
    cis: Optional[list[str]]
    cis_csc_v8: Optional[list[str]]
    cis_csc_v7: Optional[list[str]]
    nist_sp_800_53: Optional[list[str]]
    iso_27001_2013: Optional[list[str]]
    cmmc_v2_0: Optional[list[str]]
    pci_dss_v3_2_1: Optional[list[str]]
    pci_dss_v4_0: Optional[list[str]]
    soc_2: Optional[list[str]]
    mitre_techniques: Optional[list[str]]
    mitre_tactics: Optional[list[str]]
    mitre_mitigations: Optional[list[str]]
    hipaa: Optional[list[str]]

    @staticmethod
    def from_dict(obj: Any) -> 'Compliance':
        _cis = None
        __cis = obj.get("cis")
        if __cis:
            _cis = [(y) for y in __cis]
        _cis_csc_v8 = None
        __cis_csc_v8 = obj.get("cis_csc_v8")
        if __cis_csc_v8:
            _cis_csc_v8 = [y for y in __cis_csc_v8]
        _cis_csc_v7 = None
        __cis_csc_v7 = obj.get("cis_csc_v7")
        if __cis_csc_v7:
            _cis_csc_v7 = [y for y in __cis_csc_v7]
        _nist_sp_800_53 = None
        __nist_sp_800_53 = obj.get("nist_sp_800-53")
        if __nist_sp_800_53:
            _nist_sp_800_53 = [y for y in __nist_sp_800_53]
        _iso_27001_2013 = None
        __iso_27001_2013 = obj.get("iso_27001-2013")
        if __iso_27001_2013:
            _iso_27001_2013 = [y for y in __iso_27001_2013]
        _cmmc_v2_0 = None
        __cmmc_v2_0 = obj.get("cmmc_v2_0")
        if __cmmc_v2_0:
            _cmmc_v2_0 = [y for y in __cmmc_v2_0]
        _pci_dss_v3_2_1 = None
        __pci_dss_v3_2_1 = obj.get("pci_dss_v3_2_1")
        if __pci_dss_v3_2_1:
            _pci_dss_v3_2_1 = [y for y in __pci_dss_v3_2_1]
        _pci_dss_v4_0 = None
        __pci_dss_v4_0 = obj.get("pci_dss_v4_0")
        if __pci_dss_v4_0:
            _pci_dss_v4_0 = [y for y in __pci_dss_v4_0]
        _soc_2 = None
        __soc_2 = obj.get("soc_2")
        if __soc_2:
            _soc_2 = [y for y in __soc_2]
        _mitre_techniques = None
        __mitre_techniques = obj.get("mitre_techniques")
        if __mitre_techniques:
            _mitre_techniques = [y for y in __mitre_techniques]
        _mitre_tactics = None
        __mitre_tactics = obj.get("mitre_tactics")
        if __mitre_tactics:
            _mitre_tactics = [y for y in __mitre_tactics]
        _mitre_mitigations = None
        __mitre_mitigations = obj.get("mitre_mitigations")
        if __mitre_mitigations:
            _mitre_mitigations = [y for y in __mitre_mitigations]
        _hipaa = None
        __hipaa = obj.get("hipaa")
        if __hipaa:
            _hipaa = [y for y in __hipaa]
        return Compliance(_cis, _cis_csc_v8, _cis_csc_v7, _nist_sp_800_53, _iso_27001_2013, _cmmc_v2_0, _pci_dss_v3_2_1, _pci_dss_v4_0, _soc_2, _mitre_techniques, _mitre_tactics, _mitre_mitigations, _hipaa)


@dataclass
class Check:
    compliance: Optional[list[Compliance]]
    condition: str
    description: Optional[str]
    id: int
    impact: str
    rationale: Optional[str]
    references: Optional[list[str]]
    remediation: Optional[str]
    rules: Optional[list[str]]
    title: str
    regex_type: Optional[str]

    @staticmethod
    def from_dict(obj: Any) -> 'Check':
        _compliance = None
        __compliance = obj.get("compliance")
        if __compliance:
            _compliance = [Compliance.from_dict(y) for y in __compliance]
        _condition = str(obj.get("condition"))
        _description = None
        __description = obj.get("description")
        if __description:
            _description = str(__description)
        _id = int(obj.get("id"))
        _impact = str(obj.get("impact"))
        _rationale = None
        __rationale = obj.get("rationale")
        if _rationale:
            _rationale = str(__rationale)
        _references = None
        __references = obj.get("references")
        if __references:
            _references = [y for y in __references]
        _remediation = None
        __remediation = obj.get("remediation")
        if __remediation:
            _remediation = str(__remediation)
        _rules = None
        __rules = obj.get("rules")
        if __rules:
            _rules = [y for y in __rules]
        _title = str(obj.get("title"))
        _regex_type = None
        __regex_type = obj.get("regex_type")
        if __regex_type:
            _regex_type = str(__regex_type)
        return Check(_compliance, _condition, _description, _id, _impact, _rationale, _references, _remediation, _rules, _title, _regex_type)


@dataclass
class Policy:
    description: str
    file: str
    id: str
    name: str
    references: Optional[list[str]]
    regex_type: Optional[str]

    @staticmethod
    def from_dict(obj: Any) -> 'Policy':
        _description = str(obj.get("description"))
        _file = str(obj.get("file"))
        _id = str(obj.get("id"))
        _name = str(obj.get("name"))
        _references = None
        __references = obj.get("references")
        if __references:
            _references = [y for y in __references]
        _regex_type = None
        __regex_type = obj.get("regex_type")
        if __regex_type:
            _regex_type = str(__regex_type)
        return Policy(_description, _file, _id, _name, _references, _regex_type)


@dataclass
class Requirements:
    condition: str
    description: str
    rules: Optional[list[str]]
    title: str

    @staticmethod
    def from_dict(obj: Any) -> 'Requirements':
        _condition = str(obj.get("condition"))
        _description = str(obj.get("description"))
        _rules = None
        __rules = obj.get("rules")
        if __rules:
            _rules = [y for y in __rules]
        _title = str(obj.get("title"))
        return Requirements(_condition, _description, _rules, _title)


@dataclass
class SCA:
    checks: list[Check]
    policy: Policy
    requirements: Requirements
    variables: Optional[dict]

    @staticmethod
    def from_dict(obj: Any) -> 'SCA':
        _checks = [Check.from_dict(y) for y in obj.get("checks")]
        _policy = Policy.from_dict(obj.get("policy"))
        _requirements = Requirements.from_dict(obj.get("requirements"))
        _variables = None
        __variables = obj.get("variables")
        if __variables:
            _variables = dict(__variables)
        return SCA(_checks, _policy, _requirements, _variables)
