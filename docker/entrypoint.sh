#!/bin/bash

cd /mapproxy

# create config files if they do not exist yet
if [ ! -f config/mapproxy.yaml ]; then
  echo "No mapproxy configuration found. Creating one from template."
  mapproxy-util create -t base-config config
fi

exec "$@"
