#!/bin/sh

cd /mapproxy

# create config files if they do not exist yet
if [ ! -f /mapproxy/config/mapproxy.yaml ] && [ "$MULTIAPP_MAPPROXY" != "true" ]; then
  echo "No mapproxy configuration found. Creating one from template."
  mapproxy-util create -t base-config /mapproxy/config/
fi

exec "$@"
