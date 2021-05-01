#!/bin/bash

export INFLUX_HOST="INFLUX_IP"
export INFLUX_PORT=8086
export INFLUX_ORGANIZATION="influx_org"
export INFLUX_BUCKET="influx_bucket"
export INFLUX_SERVICE_TAG="influx_service_tag"
export INFLUX_TOKEN="influx_token"
export UNBOUND_HOSTS="ip1:port1:tag1:G,ip2:port2:tag2:S,ip3:port3:tag3:N"
export RUN_EVERY_SECONDS=10
export VERBOSE="True"
# Create this folder and the required subfolders (see README.md for more info)
export CONFIG_DIR="./etc/unbound"

python3 ./unbound-to-influxdb2.py $*
