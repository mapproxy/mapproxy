#!/bin/bash


# there is asumption you are running as user and that you already have installed redis package
# i run this on openSUSE tumbleweed and "it just works for me" so...

source config.sh
# Create minimal configuration file
> $REDIS_CONF
echo "port $REDIS_PORT" >> $REDIS_CONF
echo "" >> $REDIS_CONF

set +x
$REDIS_SERVER $REDIS_CONF


