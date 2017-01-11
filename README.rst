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
