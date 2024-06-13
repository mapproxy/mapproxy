#!/bin/bash

cd /mapproxy

groupadd mapproxy && \
useradd --home-dir /mapproxy -s /bin/bash -g mapproxy mapproxy && \
chown -R mapproxy:mapproxy /mapproxy/config/cache_data

# create config files if they do not exist yet
if [ ! -f /mapproxy/config/mapproxy.yaml ]; then
  echo "No mapproxy configuration found. Creating one from template."
  mapproxy-util create -t base-config config
fi

su mapproxy -c "$@"
