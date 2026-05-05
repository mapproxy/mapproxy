#!/bin/sh

# this uses a workaround for `wait -n` as this is only available in bash, which is not available on alpine

#set done to 1 if a TERM or INT signal is sent
done=0
trap 'done=1' TERM INT

# uwsgi.conf reads these via $(VAR) expansion, so they must be exported
export UWSGI_PROCESSES="${UWSGI_PROCESSES:-2}"
export UWSGI_THREADS="${UWSGI_THREADS:-10}"

UWSGI_ADD_OPTIONS=""
if [ -n "$MAPPROXY_ALPINE" ]; then
  UWSGI_ADD_OPTIONS="--plugin python3"
fi

# run uswgi and nginx in parallel
uwsgi $UWSGI_ADD_OPTIONS --ini /mapproxy/uwsgi.conf &
echo "uswgi started"
nginx &
echo "nginx started"

# check once a second if done is set
while [ $done = 0 ]; do
  sleep 1 &
  wait
done
