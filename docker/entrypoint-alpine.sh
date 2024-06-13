#!/bin/sh

cd /mapproxy

addgroup -S mapproxy && \
  adduser -D -s /bin/sh -S -h /mapproxy/ -G mapproxy mapproxy && \
  mkdir -p /var/cache/nginx/ /mapproxy/config/cache_data/ && \
  chown -R mapproxy:mapproxy /mapproxy/config/ /var/cache/nginx/

# create config files if they do not exist yet
if [ ! -f /mapproxy/config/mapproxy.yaml ]; then
  echo "No mapproxy configuration found. Creating one from template."
  mapproxy-util create -t base-config config
fi

su mapproxy -c "$@"
