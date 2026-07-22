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

export PATRONI_NAME
export PATRONI_ETCD3_HOSTS

exec patroni /etc/patroni.yml
