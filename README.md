# Sources

You can find Dockerfile and unbound-to-influxdb2.py sources on GitHub => https://github.com/MightySlaytanic/unbound2influxdb2

# Docker Hub Image

https://hub.docker.com/repository/docker/giannicostanzi/unbound2influxdb2

# Base Image

The base image is the official *python:3.9.4-alpine* on top of which we install *influxdb_client* and *unbound_console*  (via *pip*).

# Environment Variables

| Variable | Values |Default|
|-------------|-----------|-----------|
| INFLUX_HOST|IP, DNS or Docker Container/Service name of InfluxDB2 Server |IP_OR_NAME *// must be changed //*|
| INFLUX_PORT|Port on which InfluxDB2 server is listening, usually 8086 |PORT *// must be changed //*|
| INFLUX_ORGANIZATION| Organization set in InfluxDB2 |ORGANIZATION *// must be changed //*|
| INFLUX_BUCKET | Bucket on InfluxDB2 server where measurements will be stored |BUCKET *// must be changed //*|
| INFLUX_TOKEN | InfluxDB2 access token to write data on *INFLUX_BUCKET* |TOKEN *// must be changed //*|
| INFLUX_SERVICE_TAG | Name assigned to the *service* tag assigned to every record sent to InfluxDB2 | unbound
| CONFIG_DIR | Directory within the container in which unbound certs and keys are to be found | /etc/unbound (*must be mounted unless all the unbound servers do not use encryption for control traffic*) |
| UNBOUND_HOSTS | Comma separated list of Unbound hosts definition, each of which is written in format *IP_OR_NAME:PORT:HOST_TAG:ENC_FLAG*"|ip1:port1:name1:enc_flag,ip2:port2:name2:enc_flag *// must be changed //*|
| RUN_EVERY_SECONDS | Unbound polling time | 10
| VERBOSE | Increase logging output (not so verbose BTW) |false

*UNBOUND_HOSTS*: this variable can be set for example to *192.168.0.1:8953:rpi2:S,raspberry.home:8953:rpi3:G,unbound-container:8953:un-container:N* which in turn configures the container to poll every *RUN_EVERY_SECONDS* the following Unbound servers:
* 192.168.0.1 which listens on 8953/TCP and using rpi2 as *host* tag attached to the data sent to InfluxDB2
* raspberry.home (DNS name) which listens on 8953/TCP and using rpi3 as *host* tag
* unbound-container which listens on 8953/TCP and using un-container as *host* tag. In this case *unbound-container* must be a container running on the same *non-default bridge network* on which this *unbound2influxdb2* container is running in order to have docker's name resolution working as expected and the port specified is the default 8953/TCP port on which unbound official image is listening, not the port on which you expose it.


The Encryption Flag (ENC_FLAG) can be one of **S** (specific), **G** (global) and **N** (none) and it specifies for each host where to find *unbound_control.key*, *unbound_control.pem* and *unbound_server.pem* which are necessary to connect via SSL to the unbound control port, if configured to use SSL:
* S: looks for the files within $CONFIG_DIR/$HOST_TAG, so in the example above for 192.168.0.1 it looks within /etc/unbound/rpi2
* G: looks for the files within $CONFIG_DIR, so for raspberry.home it looks within /etc/unbound
* N: it does not use SSL, so connection will not be encrypted.

With the previous example, you have to mount a local folder with the following files:

    LOCAL_FOLDER/unbound_server.pem
    LOCAL_FOLDER/unbound_control.pem
    LOCAL_FOLDER/unbound_control.key
    LOCAL_FOLDER/rpi2/unbound_server.pem
    LOCAL_FOLDER/rpi2/unbound_control.pem
    LOCAL_FOLDER/rpi2/unbound_control.key

*NOTE*: you must specify S or G if the unbound service is configured with *control-use-cert: yes*, which is the default, otherwise if that option is set to *no* you must specify N. In a small home setup you can have the same *.key* and *.pem* files (also *unbound_server.key* which is not needed by this container) used by all your *unbound* services, but this is your choice. BTW, if you want to use SSL and your Unbound service is running within a container, you can get the files from a running container named *secns-unbound1* with the following command

    # The path within the container is valid for secns/unbound image, adjust it with your unbound image
    mkdir temp
    docker cp secns-unbound1:/usr/local/etc/unbound/unbound_control.key temp/
    docker cp secns-unbound1:/usr/local/etc/unbound/unbound_control.pem temp/
    docker cp secns-unbound1:/usr/local/etc/unbound/unbound_server.pem temp/
    # The following is not needed by unbound2influxdb2 image, you can retrieve 
    # it if you need to use the same SSL files on another unbound instance
    docker cp secns-unbound1:/usr/local/etc/unbound/unbound_server.key temp/

# Usage example

You can specify *-t* option which will be passed to **/unbound-to-influxdb2.py** within the container to output all the values obtained from unbound servers to screen, without uploading nothing to the influxdb server. Remember to specify *-t* also as *docker run* option in order to see the output immediately (otherwise it will be printed on output buffer flush)

    docker run -t --rm \
    -e INFLUX_HOST="influxdb_server_ip" \
    -e INFLUX_PORT=8086 \
    -e INFLUX_ORGANIZATION="org-name" \
    -e INFLUX_BUCKET="bucket-name" \
    -e INFLUX_SERVICE_TAG="unbound-test" \
    -e INFLUX_TOKEN="influx_token" \
    -e UNBOUND_HOSTS="p1:port1:tag_name1:enc_flag,ip2:port2:tag_name2:enc_flag" \
    -e CONFIG_DIR="/etc/unbound" \
    -e VERBOSE="True" \
    -v /LOCAL_PATH/etc/unbound:/etc/unbound \
    giannicostanzi/unbound2influxdb2 -t


If you remove the *-t* option passed to the container, collected data will be uploaded to influxdb bucket in a *stats*measurement. The following is an example of a non-debug run:

    docker run -d  --name="unbound2influxdb2-stats" \
	-e INFLUX_HOST="192.168.0.1" \
	-e INFLUX_PORT="8086" \
	-e INFLUX_ORGANIZATION="org-name" \
	-e INFLUX_BUCKET="bucket-name" \
    -e INFLUX_SERVICE_TAG="unbound-test" \
	-e INFLUX_TOKEN="XXXXXXXXXX_INFLUX_TOKEN_XXXXXXXXXX" \
	-e UNBOUND_HOSTS="192.168.0.2:50080:rpi3,192.168.0.3:80:rpi4" \
	-e RUN_EVERY_SECONDS="60" \
    -e CONFIG_DIR="/etc/unbound" \
	-e INFLUX_SERVICE_TAG="my_service_tag"
	giannicostanzi/unbound2influxdb2

These are the *fields* uploaded for *stats* measurement (I'll show the influxdb query used to view them all):
   
    from(bucket: "dns-resolvers-bucket")
      |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
      |> filter(fn: (r) => r["_measurement"] == "stats")
      |> filter(fn: (r) => r["service"] == "unbound")
      |> filter(fn: (r) => 
        r["_field"] == "num_cachehits" 
        or r["_field"] == "num_cachemiss" 
        or r["_field"] == "num_expired" 
        or r["_field"] == "num_prefetch" 
        or r["_field"] == "num_queries" 
        or r["_field"] == "num_queries_ip_ratelimited" 
        or r["_field"] == "num_recursivereplies" 
        or r["_field"] == "percent_cachehits" 
        or r["_field"] == "recursion_time_avg" 
        or r["_field"] == "recursion_time_median" 
        or r["_field"] == "requestlist_current_all" 
        or r["_field"] == "requestlist_avg" 
        or r["_field"] == "requestlist_current_user" 
        or r["_field"] == "requestlist_exceeded" 
        or r["_field"] == "requestlist_max" 
        or r["_field"] == "requestlist_overwritten" 
        or r["_field"] == "tcpusage" 
        or r["_field"] == "uptime")

Each record has also a tag named *host* that contains the names passed in *UNBOUND_HOSTS* environment variable and a *service* tag named as the *INFLUX_SERVICE_TAG* environment variable.

# Healthchecks

I've implemented an healthcheck that sets the container to unhealthy as long as there is at least one Unbound server that can't be queried or if there are problems uploading stats to influxdb2 server. The container becomes *healthy* in about 30 seconds if everything is fine and if there is a problem it produces an *unhealthy* status within 90 seconds.

If the container is unhealthy (you can see its status via *docker ps* command) you can check the logs with *docker logs CONTAINER_ID*

**Note:** if you have problems with the healthcheck not changing to unhealthy when it should (you see errors in the logs, for example) have a look at the health check reported by *docker inspect CONTAINER_ID* if matches the following one:

        "Healthcheck": {
                "Test": [
                    "CMD-SHELL",
                    "grep OK /healthcheck || exit 1"
                ],
                "Interval": 30000000000,
                "Timeout": 3000000000,
                "Retries": 3
            }

I'm using *Watchtower* container to update my containers automatically and I've seen that even if the image is updated, the new container still uses the old HEALTHCHECK. If it happens, just stop and remove the container and re-create it.
