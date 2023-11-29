#!/bin/bash

source config.sh

# there is asumption you are running as user and that you already have installed redis package
# i run this on openSUSE tumbleweed and "it just works for me" so...

# Create TLS directory
mkdir -p $TLS_DIR
cd $TLS_DIR

# Generate CA key and cert
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -subj "/CN=RedisCA" -days 1024 -out ca.crt

# Generate Redis server key and CSR
openssl genrsa -out redis-server.key 4096
openssl req -new -key redis-server.key -subj "/CN=$HOSTNAME" -out redis-server.csr

# Server cert config
cat > server-cert.conf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = req_ext
prompt = no

[req_distinguished_name]
CN = $HOSTNAME

[req_ext]
subjectAltName = @alt_names

[alt_names]
DNS.1 = $HOSTNAME
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

# Sign server CSR with CA
openssl x509 -req -in redis-server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out redis-server.crt -days 365 -sha256 -extfile server-cert.conf

# Generate Redis client key and CSR
openssl genrsa -out redis-client.key 4096
openssl req -new -key redis-client.key -subj "/CN=RedisClient" -out redis-client.csr

# Sign client CSR with CA
openssl x509 -req -in redis-client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out redis-client.crt -days 365 -sha256

cd -

# Create minimal configuration file
> $REDIS_TLS_CONF
echo "tls-port $REDIS_TLS_PORT" >> $REDIS_TLS_CONF
echo "port 0" >> $REDIS_TLS_CONF
echo "" >> $REDIS_TLS_CONF
echo "tls-cert-file $TLS_DIR/redis-server.crt" >> $REDIS_TLS_CONF
echo "tls-key-file $TLS_DIR/redis-server.key" >> $REDIS_TLS_CONF
echo "tls-ca-cert-file $TLS_DIR/ca.crt" >> $REDIS_TLS_CONF
echo "tls-auth-clients no" >> $REDIS_TLS_CONF

echo "Redis has been configured with TLS!"

set +x
$REDIS_SERVER $REDIS_TLS_CONF
