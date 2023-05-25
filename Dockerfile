FROM python:3.12.0b1-alpine3.17 AS builder
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --upgrade pip && pip3 install --user --no-cache-dir -r /tmp/requirements.txt

FROM python:3.12.0b1-alpine3.17
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local:$PATH
COPY unbound-to-influxdb2.py /unbound-to-influxdb2.py
COPY healthcheck /healthcheck
ENV VERBOSE="false" 
ENV CONFIG_DIR="/etc/unbound"
ENV RUN_EVERY_SECONDS="10" 
ENV INFLUX_HOST="IP_OR_NAME" 
ENV INFLUX_PORT="PORT" 
ENV INFLUX_ORGANIZATION="ORGANIZATION" 
ENV INFLUX_BUCKET="BUCKET" 
ENV INFLUX_TOKEN="TOKEN" 
ENV UNBOUND_HOSTS="ip1:port1:name1:enc_flag,ip2:port2:name2:enc_flag" 
ENV INFLUX_SERVICE_TAG="unbound"
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
            CMD grep OK /healthcheck || exit 1
ENTRYPOINT [ "python", "/unbound-to-influxdb2.py" ]
