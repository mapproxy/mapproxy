#!/bin/bash

source config.sh
# there is asumption you are running as user and that you already have installed redis package
# i run this on openSUSE tumbleweed and "it just works for me" so...


# Create minimal configuration file
> $REDIS_AUTH_CONF
echo "port $REDIS_AUTH_PORT" >> $REDIS_AUTH_CONF
echo "" >> $REDIS_AUTH_CONF
echo "requirepass $MASTER_PASSWORD" >> $REDIS_AUTH_CONF

# do trickery for creating test user....
(
        sleep 5;
        $REDIS_CLI -h $HOSTNAME -p $REDIS_AUTH_PORT -a $MASTER_PASSWORD <<EOF
ACL SETUSER $USERNAME on >$USER_PASSWORD ~* +@all
EOF
)&

echo "Redis has been configured with authentication!"

set +x
$REDIS_SERVER $REDIS_AUTH_CONF
