#!/bin/sh

# this uses a workaround for `wait -n` as this is only available in bash, which is not available on alpine

#set done to 1 if a TERM or INT signal is sent
done=0
trap 'done=1' TERM INT

# uwsgi.conf reads these via $(VAR) expansion, so they must be exported
export UWSGI_PROCESSES="${UWSGI_PROCESSES:-2}"
export UWSGI_THREADS="${UWSGI_THREADS:-10}"

# uWSGI is installed via pip in all images and has the python plugin built in
/mapproxy/.local/bin/uwsgi --ini /mapproxy/uwsgi.conf &
echo "uwsgi started"
nginx &
echo "nginx started"

# check once a second if done is set
while [ $done = 0 ]; do
  sleep 1 &
  wait
done
