import csv
import io
import json
import operator
from typing import Iterable, Optional, Any

from pkilint import validation
from pkilint.validation import ValidationFindingSeverity, ValidationResult, ValidationFindingDescription


class ReportGeneratorBase:
    def __init__(self, results: Iterable[ValidationResult], severity_threshold: Optional[ValidationFindingSeverity],
                 report_context: Optional[Any] = None):
        self.results = results
        self.severity_threshold = severity_threshold
        self.report_context = report_context

    def get_finding_descriptions_for_result(self, result):
        return [f for f in result.finding_descriptions
                if self.severity_threshold is None or f.finding.severity <= self.severity_threshold
                ]

    def is_relevant_result(self, result):
        return self.severity_threshold is None or any(self.get_finding_descriptions_for_result(result))

    def handle_result(self, result) -> Optional[Any]:
        pass

    def handle_finding_description(self, result: ValidationResult, finding_description: ValidationFindingDescription,
                                   result_context: Optional[Any]):
        pass

    def generate(self):
        for result in self.results:
            result_context = self.handle_result(result)

            for finding_description in self.get_finding_descriptions_for_result(result):
                self.handle_finding_description(result, finding_description, result_context)


class ReportGeneratorPlaintext(ReportGeneratorBase):
    def __init__(self, results, severity_threshold):
        super().__init__(results, severity_threshold, io.StringIO())

    def handle_result(self, result):
        if self.is_relevant_result(result):
            self.report_context.write( f'{result.validator} @ {result.node.path}\n')

    def handle_finding_description(self, result: ValidationResult, finding_description: ValidationFindingDescription,
                                   result_context: Optional[Any]):
        self.report_context.write(f'    {finding_description}\n')

    def generate(self):
        super().generate()

        return self.report_context.getvalue()


class ReportGeneratorCsv(ReportGeneratorBase):
    _CSV_FIELDNAMES = ['node_path', 'validator', 'severity', 'code', 'message']

    def __init__(self, results, severity_threshold, output_headers=True):
        self._output_io = io.StringIO()

        output_csv = csv.DictWriter(self._output_io, fieldnames=self._CSV_FIELDNAMES)

        if output_headers:
            output_csv.writeheader()

        super().__init__(results, severity_threshold, output_csv)


    def handle_finding_description(self, result, finding_description, result_context):
        row = {
            'node_path': result.node.path,
            'validator': str(result.validator),
            'severity': finding_description.finding.severity.name,
            'code': finding_description.finding.code,
            'message': '' if finding_description.message is None else finding_description.message
        }

        self.report_context.writerow(row)

    def generate(self):
        super().generate()

        return self._output_io.getvalue()


class ReportGeneratorJson(ReportGeneratorBase):
    def __init__(self, results, severity_threshold):
        super().__init__(results, severity_threshold, [])

    def handle_result(self, result) -> Optional[Any]:
        if self.is_relevant_result(result):
            result_dict = {
                'node_path': result.node.path,
                'validator': str(result.validator),
                'finding_descriptions': []
            }

            self.report_context.append(result_dict)

            return result_dict['finding_descriptions']

    def handle_finding_description(self, result: ValidationResult, finding_description: ValidationFindingDescription,
                                   result_context: Optional[Any]):
        for finding_description in self.get_finding_descriptions_for_result(result):
            result_context.append(
                {
                    'severity': finding_description.finding.severity.name,
                    'code': finding_description.finding.code,
                    'message': finding_description.message,
                }
            )

    def generate(self):
        super().generate()

        return json.dumps({'results': self.report_context})


def get_findings_count(results: Iterable[ValidationResult],
                       severity_threshold: ValidationFindingSeverity = None
                       ):
    findings = 0
    for result in results:
        for finding in result.finding_descriptions:
            if severity_threshold is None or finding.finding.severity <= severity_threshold:
                findings += 1

    return findings


def report_wrapper(report_generator_cls, *args, **kwargs):
    report_generator = report_generator_cls(*args, **kwargs)

    return report_generator.generate()


REPORT_FORMATS = {
    'TEXT': ReportGeneratorPlaintext,
    'CSV': ReportGeneratorCsv,
    'JSON': ReportGeneratorJson,
}


_VALIDATION_LIST_CSV_FIELDNAMES = ['severity', 'code']

def _validation_sorter(a, b):
    diff = a.severity - b.severity

    if diff != 0:
        return diff

    return a.code < b.code


def report_included_validations(*args):
    s = io.StringIO()

    c = csv.DictWriter(s, fieldnames=_VALIDATION_LIST_CSV_FIELDNAMES)
    c.writeheader()

    all_validations = set()
    for validator in args:
        all_validations.update(validator.validations)

    validations = sorted(all_validations, key=lambda v: f'{int(v.severity)}-{v.code}')

    for v in validations:
        c.writerow({'severity': str(v.severity), 'code': v.code})

    return s.getvalue()
