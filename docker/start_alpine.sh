#!/bin/sh

TARGET=$1
done=0
trap 'done=1' TERM INT
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

if [ "$TARGET" = "nginx" ]; then
  su mapproxy -c "uwsgi --ini /mapproxy/uwsgi.conf --uid mapproxy &"
  nginx &
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
