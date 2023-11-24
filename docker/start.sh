#!/bin/bash

TARGET=$1
done=0
trap 'done=1' TERM INT
cd /mapproxy

groupadd mapproxy && \
useradd --home-dir /mapproxy -s /bin/bash -g mapproxy mapproxy && \
chown -R mapproxy:mapproxy /mapproxy/config/cache_data

# create config files if they do not exist yet
if [ ! -f /mapproxy/config/mapproxy.yaml ]; then
  echo "No mapproxy configuration found. Creating one from template."
  mapproxy-util create -t base-config config
fi

if [ "$TARGET" = "nginx" ]; then
  service nginx restart &&
  su mapproxy -c "/usr/local/bin/uwsgi --ini /mapproxy/uwsgi.conf &"
elif [ "$TARGET" = 'development' ]; then
  su mapproxy -c "mapproxy-util serve-develop -b 0.0.0.0 /mapproxy/config/mapproxy.yaml &"
else
  echo "No-op container started. Overwrite ENTRYPOINT with needed mapproxy command."
  su mapproxy -c "sleep infinity &"
fi

while [ $done = 0 ]; do
  sleep 1 &
  wait
done
