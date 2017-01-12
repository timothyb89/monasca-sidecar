===============================
monasca-sidecar
===============================

A minimal metric forwarder bridging Monasca and Prometheus.

This project provides a minimalistic metric forwarder for applications
instrumented using a Prometheus client, such as the `Python prometheus client
<https://github.com/prometheus/client_python>`_. When run alongside an
instrumented application, it ingests, aggregates, and re-publishes Prometheus-
compatible metrics that can be scraped by something like the `Monasca agent
<https://github.com/openstack/monasca-agent>`_. Any number of application
threads or isolated instances can write to the sidecar server and will appear
as a single application to the rest of the metrics pipeline.

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/monasca-sidecar
* Source: http://git.openstack.org/cgit/openstack/monasca-sidecar
* Bugs: http://bugs.launchpad.net/monasca

Features
--------

* Solves common complexities with mutiprocess applications: all instances can
  write to the sidecar server concurrently.
* Can perform simple aggregations on metrics across all client instances,
  reducing the metric
* Targets Docker and particularly Kubernetes environments

Note that this project requires Python versions >= 3.5.

Quickstart
----------

If you have a Docker environment available, you can try it out immediately:

.. code-block:: bash

    docker run --rm=true -p 4888:4888 -it timothyb89/monasca-sidecar:1.0.0

To write a metric with `HTTPie <https://github.com/jkbrzt/httpie>`_, use:

.. code-block:: bash

    echo '[
      {
        "name": "test",
        "type": "gauge",
        "help": "test description",
        "values": [
          { "name": "test", "labels": {"c": "d"}, "value": 12.34 }
        ]
      }
    ]' | http post localhost:4888/v1/ingest

To view the published Prometheus metrics, run:

.. code-block:: bash

    http get http://localhost:4888/metrics

Aggregation
-----------

Simple metric aggregation across an :code:`_id` label can be performed. To do
so, add an extra :code:`_aggregate` label with a value of the desired
aggregation function, such as :code:`sum`, :code:`mean`, :code:`min`, or
:code:`max`. Then, when requesting the :code:`/metrics` endpoint, metrics with
identical labels (excluding :code:`_id` and :code:`_aggregate`) will be
combined.

Metric Decay
------------

By default, submitted metrics decay after 60 seconds if they are no longer
updated. In other words, if a particular combination of (metric name + labels)
is not updated for 60 seconds, it will be removed from the reported metric list
and will no affect any aggregations. This is intended to allow subprocesses to
start and stop (intentionally or otherwise) without needing to inform the
sidecar server about their lifecycles directly.

Note that subprocesses should carefully select values for their :code:`_id`
labels to make best use of this feature - a UUID4 is recommended for best
results, though in some cases a PID can work fine.

This value can be configured by changing the :code:`DECAY_SECONDS` environment
variable before starting the sidecar server.

Docker and Kubernetes
---------------------

A working Dockerfile is provided that will run a simple sidecar server. This
can easily be made available to a Kubernetes pod over :code:`localhost`.

As an example, consider a Prometheus-client instrumented Python application
that exposes a RESTful API. It uses `gunicorn <http://gunicorn.org/>`_ and has
several worker processes. A Kubernetes deployment might look like the following:

.. code-block:: yaml

    apiVersion: extensions/v1beta1
    kind: Deployment
    metadata:
      name: some-python-api
      namespace: api
    spec:
      replicas: 1
      template:
        metadata:
          labels:
            app: monasca-api
        spec:
          containers:
            - name: some-python-api
              image: some-user/some-python-api:1.0
              ports:
                - containerPort: 8080
                  name: http

To make a sidecar available, add another container to the deployment spec like
so:

.. code-block:: yaml

    apiVersion: extensions/v1beta1
    kind: Deployment
    metadata:
      name: some-python-api
      namespace: api
    spec:
      replicas: 1
      template:
        metadata:
          labels:
            app: monasca-api
        spec:
          containers:
            - name: some-python-api
              image: some-user/some-python-api:1.0
              ports:
                - containerPort: 8080
                  name: http
            - name: monasca-sidecar
              image: timothyb89/monasca-sidecar:1.0
              ports:
                - containerPort: 4888
                  name: scrape

Now, the :code:`some-python-api` application can POST metrics to the sidecar's
REST API at :code:`http://localhost:4888/ingest`, and the processed metrics will
be published at :code:`http://localhost:4888/metrics`.
