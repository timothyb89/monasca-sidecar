from io import StringIO
from typing import Dict

import hug


class MetricValue(object):
    def __init__(self, name: str, labels: Dict[str, str]):
        self.name = name
        self.labels = labels

        self._value = None

    def matches(self, name: str, labels: Dict[str, str]) -> bool:
        if name != self.name:
            return False

        if len(labels) != len(self.labels):
            return False

        for k, v in labels.items():
            if k not in self.labels or v != self.labels[k]:
                return False

        return True

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def format_name(self):
        if len(self.labels) is 0:
            return self.name
        else:
            labels = map(lambda t: '{}="{}"'.format(t[0], t[1]),
                         self.labels.items())

            return '{}{{{}}}'.format(self.name,
                                     ','.join(labels))

    def __repr__(self):
        return "%s(name=%r, value=%r, labels=%r)" % (
            self.__class__.__name__,
            self.name,
            self.value,
            self.labels
        )


class MetricDefinition(object):
    def __init__(self, name: str, metric_type: str, metric_help: str):
        self.name = name
        self.metric_type = metric_type
        self.metric_help = metric_help

        self.children = {}

    def update(self, defs):
        for metric in defs:
            metric_name = metric['name']
            metric_labels = metric['labels']

            value_list = self.children.get(metric_name, None)
            if value_list is None:
                value_list = []
                self.children[metric_name] = value_list

            value = next(filter(lambda v: v.matches(metric_name, metric_labels),
                                value_list), None)
            if not value:
                value = MetricValue(metric_name, metric_labels)
                value_list.append(value)

            value.value = metric['value']

    def __repr__(self):
        return "%s(name=%r, metric_type=%r, metric_help=%r, children=%r)" % (
            self.__class__.__name__,
            self.name,
            self.metric_type,
            self.metric_help,
            self.children
        )

METRICS = {}


def get_or_define_metric(template) -> MetricDefinition:
    name = template['name']
    if name in METRICS:
        return METRICS[name]

    metric_type = template['type']
    metric_help = template['help']

    metric = MetricDefinition(name, metric_type, metric_help)
    METRICS[name] = metric

    return metric


@hug.post('/ingest', versions=1, output=hug.output_format.text)
def ingest(body):
    for metric_template in body:
        metric_def = get_or_define_metric(metric_template)
        metric_def.update(metric_template['values'])


# unversioned
@hug.get('/metrics', output=hug.output_format.text)
def metrics():
    buf = StringIO()

    for mdef in METRICS.values():
        print('# HELP {} {}'.format(mdef.name, mdef.metric_help), file=buf)
        print('# TYPE {} {}'.format(mdef.name, mdef.metric_type), file=buf)
        for _, bucket in mdef.children.items():
            for child in bucket:
                print('{} {}'.format(child.format_name(), child.value), file=buf)

        print('', file=buf)

    return buf.getvalue()
