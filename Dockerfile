from python:3.5-alpine

copy monasca_sidecar /monasca_sidecar
copy requirements.txt /sidecar_requirements.txt

run pip install -r /sidecar_requirements.txt

env DECAY_SECONDS="60"

expose 4888
cmd hug -p 4888 -f /monasca_sidecar/sidecar.py
