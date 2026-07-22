FROM postgres:16

RUN apt-get update \
    && apt-get install -y python3 python3-pip curl jq --no-install-recommends \
    && pip3 install --break-system-packages psycopg2-binary patroni[etcd] \
    && rm -rf /var/lib/apt/lists/*

ENV ETCDVERSION=3.5.18

RUN arch=$(dpkg --print-architecture) \
    && curl -sL "https://github.com/etcd-io/etcd/releases/download/v${ETCDVERSION}/etcd-v${ETCDVERSION}-linux-${arch}.tar.gz" \
        | tar xz -C /usr/local/bin --strip=1 --wildcards --no-anchored etcd etcdctl

COPY patroni.yml /etc/patroni.yml
COPY entrypoint.sh /entrypoint.sh

ENV PATRONI_CONFIG_FILE=/etc/patroni.yml

RUN chmod +x /entrypoint.sh \
    && mkdir -p /data/postgres \
    && chown -R postgres:postgres /data /etc/patroni.yml

USER postgres

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
