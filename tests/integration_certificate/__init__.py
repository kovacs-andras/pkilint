import csv
import io
import typing
from os import path
from pathlib import Path

from pkilint import loader, validation

_FIXTURE_DIR = Path(__file__).parent.resolve()


_CERT_END_ASCII_ARMOR = '-----END CERTIFICATE-----'


class TestFinding(typing.NamedTuple):
    node_path: str
    validator: str
    severity: validation.ValidationFindingSeverity
    code: str
    message: typing.Optional[str]

    @staticmethod
    def from_dict(d):
        return TestFinding(d['node_path'], d['validator'], validation.ValidationFindingSeverity[d['severity']],
                                d['code'], None if not d['message'] else d['message'])

    @staticmethod
    def from_result_and_finding_description(result: validation.ValidationResult,
                                            finding_description: validation.ValidationFindingDescription):
        return TestFinding(
            result.node.path,
            str(result.validator),
            finding_description.finding.severity,
            finding_description.finding.code,
            finding_description.message
        )


def certificate_test_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip() != '']

    assert any((_CERT_END_ASCII_ARMOR in line for line in lines))

    pem_text = ''

    line_num = -1
    for line_num, line in enumerate(lines):
        pem_text += line

        if _CERT_END_ASCII_ARMOR in line:
            break

    s = io.StringIO('\n'.join(lines[line_num + 1:]))

    c = csv.DictReader(s)

    expected_findings = set((TestFinding.from_dict(row) for row in c))

    cert = loader.load_pem_certificate(pem_text, path.basename(file_path))
    cert.decode()

    return cert, expected_findings


def run_test(test_file_path, validator):
    cert, expected_findings = certificate_test_file(test_file_path)

    results = validator.validate(cert.root)

    actual_findings = set()

    for result in results:
        finding_descriptions = [fd for fd in result.finding_descriptions]

        for finding_description in finding_descriptions:
            actual_findings.add(TestFinding.from_result_and_finding_description(result, finding_description))

    missing_findings = expected_findings - actual_findings

    assert len(missing_findings) == 0, f'Missing findings: {missing_findings}'

    unexpected_findings = actual_findings - expected_findings

    assert len(unexpected_findings) == 0, f'Unexpected findings: {unexpected_findings}'
