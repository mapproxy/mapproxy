# Variables
REDIS_CONF="redis.conf"
REDIS_AUTH_CONF="redis_auth.conf"
REDIS_TLS_CONF="redis_tls.conf"
REDIS_CLI="/usr/bin/redis-cli"
REDIS_SERVER="/usr/sbin/redis-server"
REDIS_PORT=6379
REDIS_TLS_PORT=6380
REDIS_AUTH_PORT=6381

TLS_DIR="../unit/fixture"
HOSTNAME=$(hostname -f)
MASTER_PASSWORD="solarwinds123" # Master password for Redis

USERNAME="test"
USER_PASSWORD="pw4test"
