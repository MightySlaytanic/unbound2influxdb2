#!/usr/bin/python3

# "unbound_control stats" output example:
#total.num.queries=134
#total.num.queries_ip_ratelimited=0
#total.num.cachehits=63
#total.num.cachemiss=71
#total.num.prefetch=4
#total.num.expired=1
#total.num.recursivereplies=65
#total.requestlist.avg=4.61333
#total.requestlist.max=10
#total.requestlist.overwritten=0
#total.requestlist.exceeded=0
#total.requestlist.current.all=5
#total.requestlist.current.user=5
#total.recursion.time.avg=11.437197
#total.recursion.time.median=6.6
#total.tcpusage=0
#time.now=1615925310.412573
#time.up=166.173221

import sys
import json
import argparse
from datetime import datetime
from time import sleep
from os import getenv
from os.path import realpath, dirname, isfile

from unbound_console import RemoteControl
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError

SERVER_CERT_FILE = "unbound_server.pem"
CLIENT_CERT_FILE = "unbound_control.pem"
CLIENT_KEY_FILE = "unbound_control.key"

PROGRAM_DIR = dirname(realpath(__file__))
HEALTHCHECK_FILE = f"{PROGRAM_DIR}/healthcheck"
HEALTHCHECK_FAILED = "FAILED"
HEALTHCHECK_OK = "OK"

CONFIG_DIR = getenv("CONFIG_DIR")
INFLUX_HOST = getenv("INFLUX_HOST")
INFLUX_PORT = getenv("INFLUX_PORT")
INFLUX_ORGANIZATION = getenv("INFLUX_ORGANIZATION")
INFLUX_BUCKET = getenv("INFLUX_BUCKET")
INFLUX_TOKEN = getenv("INFLUX_TOKEN")
INFLUX_SERVICE_TAG = getenv("INFLUX_SERVICE_TAG")
UNBOUND_HOSTS = getenv("UNBOUND_HOSTS")
RUN_EVERY_SECONDS = int(getenv("RUN_EVERY_SECONDS"))
VERBOSE = getenv("VERBOSE")

DEBUG = 0

def set_failed_flag():
    with open(HEALTHCHECK_FILE, "w") as healthcheck_file:
        healthcheck_file.write(HEALTHCHECK_FAILED)


def set_ok_flag():
    with open(HEALTHCHECK_FILE, "w") as healthcheck_file:
        healthcheck_file.write(HEALTHCHECK_OK)


def get_ssl_files(encryption_flag, dir_name):
    server_cert, client_cert, client_key = (None, None, None)
    if encryption_flag == "G":
        server_cert = f"{CONFIG_DIR}/{SERVER_CERT_FILE}"
        client_cert = f"{CONFIG_DIR}/{CLIENT_CERT_FILE}"
        client_key = f"{CONFIG_DIR}/{CLIENT_KEY_FILE}"
    elif encryption_flag == "S":
        server_cert = f"{CONFIG_DIR}/{dir_name}/{SERVER_CERT_FILE}"
        client_cert = f"{CONFIG_DIR}/{dir_name}/{CLIENT_CERT_FILE}"
        client_key = f"{CONFIG_DIR}/{dir_name}/{CLIENT_KEY_FILE}"
    elif encryption_flag == "N":
        pass
    else:
        raise NameError(f"Invalid Encryption Flag {encryption_flag}! Allowed values are N, G or S!")

    if server_cert and client_cert and client_key:
        for file in (server_cert, client_cert, client_key):
            if not isfile(file):
                raise FileNotFoundError(f"Invalid file <{file}> specified, check UNBOUND_HOSTS definition for device with name <{dir_name}>!")

    return (server_cert, client_cert, client_key)

if __name__ == '__main__':
    if VERBOSE.lower() == "true":
        DEBUG = 1

    UNBOUND_HOSTS_DICT = {}

    for index, entry in enumerate(UNBOUND_HOSTS.split(",")):
        try:
            host, port, name, enc_flag = entry.split(":")
        except ValueError as e:
            print(e, file=sys.stderr)
            print(f"Wrong UNBOUND_HOSTS entry <{entry}>!", file=sys.stderr)
            sys.exit(1)

        server_cert, client_cert, client_key = get_ssl_files(enc_flag, name)
        UNBOUND_HOSTS_DICT.update({
            index : { 
                "host": host,
                "name": name, 
                "port": port, 
                "encryption_flag": enc_flag,
                "server_cert": server_cert,
                "client_cert": client_cert,
                "client_key": client_key
            }
        })

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting...")
    print("\nUNBOUND_HOSTS definition:\n")
    print(json.dumps(UNBOUND_HOSTS_DICT, indent=4))

    if DEBUG:
        print(f"\nHealthcheck file => {HEALTHCHECK_FILE}")

    parser = argparse.ArgumentParser(usage="UnBound Stats to influxdb2 uploader")

    parser.add_argument(
        "-t",
        "--test",
        help="Just print the results without uploading to influxdb2",
        action="store_true"
    )

    args = parser.parse_args()

    last_healthcheck_failed = False
    set_ok_flag()

    while True:
        start_time = datetime.now()
        failure = False

        for index in UNBOUND_HOSTS_DICT.keys():
            host = UNBOUND_HOSTS_DICT[index]["host"]
            host_name = UNBOUND_HOSTS_DICT[index]["name"]
            try:
                host_port = int(UNBOUND_HOSTS_DICT[index]["port"])
            except ValueError as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"Wrong port <{UNBOUND_HOSTS_DICT[index]['port']}> specified for host {host}!", file=sys.stderr)
                continue
            
            host_encryption_flag = UNBOUND_HOSTS_DICT[index]["encryption_flag"]
            host_server_cert = UNBOUND_HOSTS_DICT[index]["server_cert"]
            host_client_cert = UNBOUND_HOSTS_DICT[index]["client_cert"]
            host_client_key = UNBOUND_HOSTS_DICT[index]["client_key"]

            if DEBUG:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Collecting data for host {host}:{host_port}[ENC:{host_encryption_flag}]({host_name})...")


            try:
                rc = RemoteControl(
                    host=host, 
                    port=host_port,
                    server_cert = host_server_cert,
                    client_cert = host_client_cert,
                    client_key = host_client_key
                )

                output = rc.send_command(cmd="stats")
            except Exception as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not connect to {host}:{host_port}[ENC:{host_encryption_flag}]({host_name})",file=sys.stderr)
                continue

            stats = {}

            # Unbound on raspberry returns total.num.zero_ttl instead of total.num.expired returned by Synology secns_unbound
            # so we change zero_ttl to expired
            total_queries = 0
            total_cachehits = 0

            
            output_problem = False

            for line in output.split("\n"):
                try:
                    key, value = line.split("=")
                except ValueError as e:
                    failure = True
                    print(e, file=sys.stderr)
                    print(f"Wrong output <{output}> received from host {host}:{host_port}[ENC:{host_encryption_flag}]({host_name})!", file=sys.stderr)
                    output_problem = True
                    break

                if key.startswith("total"):
                    # Remove dots and replace with underscore. Remove also prefix total.
                    key = key[6:].replace(".", "_")
                    if key.endswith("avg") or key.endswith("median"):
                        stats[key] = float(value)
                    else:
                        if key.endswith("zero_ttl"):
                            key = key.replace("zero_ttl", "expired")
                        elif key.endswith("queries"):
                            total_queries = int(value)
                        elif key.endswith("cachehits"):
                            total_cachehits = int(value)

                        stats[key] = int(value)
                elif key == "time.up":
                    stats["uptime"] = float(value)
            
            if output_problem:
                # Skip to next host
                continue

            if total_queries == 0:
                stats["percent_cachehits"] = 0.0
            else:
                stats["percent_cachehits"] = (total_cachehits / total_queries) * 100.0
                    
            if args.test:
                print(f"\nStats for host {host}:{host_port}[ENC:{host_encryption_flag}]({host_name}): ")
                print(json.dumps(stats, indent=4))
            else:
                try:
                    if DEBUG:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Uploading data for host {host}[ENC:{host_encryption_flag}]({host_name})...")
                    client = InfluxDBClient(url=f"http://{INFLUX_HOST}:{INFLUX_PORT}", token=INFLUX_TOKEN, org="alixnetwork", timeout=10)
                    write_api = client.write_api(write_options=SYNCHRONOUS)

                    write_api.write(
                        INFLUX_BUCKET,
                        INFLUX_ORGANIZATION,
                        [
                            {
                                "measurement": "stats",
                                "tags": {"host": host_name, "service": INFLUX_SERVICE_TAG},
                                "fields": stats
                            }
                        ]
                    )
                except TimeoutError as e:
                    failure = True
                    print(e,file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TimeoutError: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}[ENC:{host_encryption_flag}]({host_name})",file=sys.stderr)
                    continue
                except InfluxDBError as e:
                    failure = True
                    print(e,file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] InfluxDBError: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}[ENC:{host_encryption_flag}]({host_name})",file=sys.stderr)
                    continue
                except Exception as e:
                    failure = True
                    print(e, file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}[ENC:{host_encryption_flag}]({host_name})",file=sys.stderr)
                    continue

                client.close()
        
        # Health check management
        if failure:
            if not last_healthcheck_failed:
                # previous cycle was successfull, so we must set the failed flag
                set_failed_flag()
                last_healthcheck_failed = True
        else:
            if last_healthcheck_failed:
                # Everything ok, clear the flag
                set_ok_flag()
                last_healthcheck_failed = False

        # Sleep for the amount of time specified by RUN_EVERY_SECONDS minus the time elapsed for the above computations
        stop_time = datetime.now()
        delta_seconds = int((stop_time - start_time).total_seconds())
        
        if delta_seconds < RUN_EVERY_SECONDS:
            sleep(RUN_EVERY_SECONDS - delta_seconds)
