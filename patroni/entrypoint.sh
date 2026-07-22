#!/bin/sh

set -e

if [ -z "$PATRONI_NAME" ]; then
    echo "PATRONI_NAME must be set"
    exit 1
fi

if [ -z "$PATRONI_ETCD3_HOSTS" ]; then
    echo "PATRONI_ETCD3_HOSTS must be set"
    exit 1
fi

chmod 0700 /data/postgres 2>/dev/null || true

export PATRONI_NAME
export PATRONI_ETCD3_HOSTS
export PATRONI_RESTAPI_CONNECT_ADDRESS="${PATRONI_NAME}:8008"
export PATRONI_POSTGRESQL_CONNECT_ADDRESS="${PATRONI_NAME}:5432"

exec patroni /etc/patroni.yml
