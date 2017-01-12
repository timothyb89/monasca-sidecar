import os
import statistics
import time

from io import StringIO
from typing import Dict, List

import hug


decay_seconds = float(os.environ.get('DECAY_SECONDS', '60'))


class MetricValue(object):
    def __init__(self, name: str, labels: Dict[str, str], value=None):
        self.name = name
        self.labels = labels

        self._value = value
        self.last_update = time.time()

    def matches(self, name: str,
                labels: Dict[str, str],
                exclude: List[str]=None) -> bool:
        if name != self.name:
            return False

        if exclude is None:
            exclude = []

        ours = {k for k in self.labels.keys() if k not in exclude}
        theirs = {k for k in self.labels.keys() if k not in exclude}
        if ours != theirs:
            return False

        for k, v in labels.items():
            if v != self.labels[k]:
                return False

        return True

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float):
        self._value = value
        self.last_update = time.time()

    def format_name(self) -> str:
        if len(self.labels) is 0:
            return self.name
        else:
            labels = map(lambda t: '{}="{}"'.format(t[0], t[1]),
                         self.labels.items())

            return '{}{{{}}}'.format(self.name,
                                     ','.join(labels))

    def __repr__(self) -> str:
        return "%s(name=%r, value=%r, labels=%r)" % (
            self.__class__.__name__,
            self.name,
            self.value,
            self.labels
        )


class AggregationBucket(object):
    def __init__(self, name: str, labels: Dict[str, str]):
        self.name = name
        self.labels = labels

        self.members = []

    def matches(self, metric: MetricValue, exclude_labels: List[str]=None):
        if exclude_labels is None:
            exclude_labels = []

        return metric.matches(self.name, self.labels, exclude_labels)

    def add(self, member):
        self.members.append(member)

    def aggregate(self):
        if len(self.members) is 1:
            return MetricValue(self.name, self.labels, self.members[0].value)

        method_name = None
        for member in self.members:
            if '_aggregate' in member.labels:
                method_name = member.labels['_aggregate']
                break

        method = {
            'sum': sum,
            'min': min,
            'max': max,
            'mean': statistics.mean
        }.get(method_name, lambda x: x[0])

        value = method([v.value for v in self.members])
        return MetricValue(self.name, self.labels, value)

    def __repr__(self) -> str:
        return "%s(name=%r, labels=%r, members=%r)" % (
            self.__class__.__name__,
            self.name,
            self.labels,
            self.members
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

    def decay(self):
        """Remove all child metrics last updated at least `decay_seconds` ago"""
        now = time.time()

        keys_to_remove = []

        for key in self.children.keys():
            self.children[key] = list(filter(
                lambda child: now - child.last_update < decay_seconds,
                self.children[key]))

            if not self.children[key]:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.children[key]

    def buckets(self, exclude_labels: List[str]=None) -> List[AggregationBucket]:
        """Splits child metrics into buckets with matching labels."""
        if not exclude_labels:
            exclude_labels = []

        buckets = []
        for value_list in self.children.values():
            for v in value_list:
                bucket = next(filter(lambda b: b.matches(v, exclude_labels),
                                     buckets), None)
                if not bucket:
                    labels = v.labels.copy()
                    for exclude in exclude_labels:
                        labels.pop(exclude, None)

                    bucket = AggregationBucket(v.name, labels)
                    buckets.append(bucket)

                bucket.add(v)

        return buckets

    def aggregate(self, fields: List[str]=None) -> List[MetricValue]:
        """Aggregates child metrics of this definition along the given fields."""
        if fields is None:
            fields = ['_id', '_aggregate']

        return [b.aggregate() for b in self.buckets(fields)]

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


@hug.post('/ingest', versions=1, output=hug.output_format.json)
def ingest(body):
    for metric_template in body:
        metric_def = get_or_define_metric(metric_template)
        metric_def.update(metric_template['values'])
        metric_def.decay()

    return True


@hug.post('/clear', versions=1, output=hug.output_format.json)
def clear():
    METRICS.clear()
    return True


# unversioned
@hug.get('/metrics', output=hug.output_format.text)
def metrics():
    buf = StringIO()

    expired_def_keys = []
    for key, mdef in METRICS.items():
        mdef.decay()
        if not mdef.children:
            expired_def_keys.append(key)

    for key in expired_def_keys:
        del METRICS[key]

    mdefs = sorted(METRICS.values(), key=lambda x: x.name)
    for mdef in mdefs:
        mdef.decay()

        print('# HELP {} {}'.format(mdef.name, mdef.metric_help), file=buf)
        print('# TYPE {} {}'.format(mdef.name, mdef.metric_type), file=buf)
        for bucket in mdef.aggregate():
            print('{} {}'.format(bucket.format_name(), bucket.value), file=buf)

        print('', file=buf)

    return buf.getvalue()
