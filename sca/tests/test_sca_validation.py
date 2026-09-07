from sca.services.sca_service import _structure_error, validate_sca_file
from sca.tests.helpers import baseline, write_yaml


def _validate(tmp_path, data):
    path = tmp_path / 'policy.yml'
    write_yaml(path, data)
    return validate_sca_file(str(path))


def test_requirements_section_is_optional(tmp_path):
    data = baseline()
    del data['requirements']
    assert _validate(tmp_path, data) == (True, None)


def test_requirements_fields_are_required_when_section_exists(tmp_path):
    data = baseline()
    data['requirements']['rules'] = ['f:/etc/passwd']
    assert _validate(tmp_path, data) == (True, None)
    del data['requirements']['rules']
    valid, message = _validate(tmp_path, data)
    assert not valid and 'requirements.rules' in message


def test_checks_require_rules_and_documented_condition(tmp_path):
    data = baseline()
    del data['checks'][0]['rules']
    valid, message = _validate(tmp_path, data)
    assert not valid and 'rules' in message

    data = baseline()
    data['checks'][0]['condition'] = 'sometimes'
    valid, message = _validate(tmp_path, data)
    assert not valid and 'condition' in message


def test_regex_type_is_limited_to_documented_engines(tmp_path):
    data = baseline()
    data['policy']['regex_type'] = 'pcre2'
    data['checks'][0]['regex_type'] = 'osregex'
    assert _validate(tmp_path, data) == (True, None)

    data['checks'][0]['regex_type'] = 'python'
    valid, message = _validate(tmp_path, data)
    assert not valid and 'regex_type' in message


def test_policy_id_accepts_documented_arbitrary_string(tmp_path):
    data = baseline()
    data['policy']['id'] = 'Custom policy ID'
    assert _validate(tmp_path, data) == (True, None)


def test_invalid_utf8_is_rejected(tmp_path):
    path = tmp_path / 'policy.yml'
    path.write_bytes(b'policy:\n  name: \xff\n')
    assert validate_sca_file(str(path)) == (False, 'Unable to parse the YAML file')


def test_python_object_tag_is_rejected_without_execution(tmp_path):
    marker = tmp_path / 'owned'
    path = tmp_path / 'policy.yml'
    path.write_text(
        '!!python/object/apply:os.system ["touch ' + str(marker) + '"]\n',
        encoding='utf-8',
    )
    assert validate_sca_file(str(path))[0] is False
    assert not marker.exists()


def test_structural_amplification_is_rejected(tmp_path):
    data = baseline()
    data['checks'][0]['rules'] = ['f:/same'] * 100_001
    valid, message = _validate(tmp_path, data)
    assert not valid
    assert message == 'SCA file is too structurally complex'


def test_nested_variables_count_toward_structure_limit(tmp_path, monkeypatch):
    monkeypatch.setattr('sca.services.sca_service.MAX_STRUCTURE_ITEMS', 90)

    flat = baseline()
    flat['variables'] = {f'$var_{index}': index for index in range(10)}
    assert _validate(tmp_path, flat) == (True, None)

    nested = baseline()
    nested['variables'] = {
        '$nested': {f'$var_{index}': {'value': index} for index in range(10)}
    }
    assert _validate(tmp_path, nested) == (False, 'SCA file is too structurally complex')


def test_unsupported_yaml_collection_is_rejected(tmp_path):
    data = baseline()
    data['variables'] = {'$unsupported': {'one', 'two'}}
    assert _validate(tmp_path, data) == (False, 'Unsupported YAML collection type')


def test_structure_budget_short_circuits_repeated_subtree():
    visited = [0]

    class CountingList(list):
        def __iter__(self):
            for item in super().__iter__():
                visited[0] += 1
                if visited[0] > 20:
                    raise AssertionError('structure walk did not short-circuit')
                yield item

    shared = CountingList(range(1_000))
    data = [shared] * 1_000
    assert _structure_error(data, 10) == 'SCA file is too structurally complex'
    assert visited[0] < 20
