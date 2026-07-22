# HA System — Dağıtık Yüksek Erişilebilirlik Sistemi

## Genel Mimari

```
Client
  -> HAProxy (LB1, client-facing) - backend health check ile round-robin
    -> Backend-1 (FastAPI)
    -> Backend-2 (FastAPI)
       -> Redis (cache)
       -> HAProxy (LB2, db-facing) - iki ayrı port/havuz:
          - WRITE havuzu (port 5000): Patroni /primary health check,
            sadece o anki primary'e gider
          - READ havuzu (port 5001): Patroni /replica health check,
            sadece replica'lara gider, primary bu havuza HİÇ girmez
          -> postgres-1 / postgres-2 / postgres-3
             (Patroni ile yönetilen, 1 primary + 2 streaming replica)
             -> etcd (Patroni'nin lider seçimi için kullandığı DCS)
```

## Servisler ve Portlar

| Servis | Port (iç) | Port (host) | Açıklama |
|---|---|---|---|
| etcd | 2379 | 2379 | Patroni DCS |
| postgres-1 | 5432, 8008 | - | Patroni node 1 |
| postgres-2 | 5432, 8008 | - | Patroni node 2 |
| postgres-3 | 5432, 8008 | - | Patroni node 3 |
| haproxy-db | 5000, 5001, 7000 | 5000, 5001, 7000 | DB load balancer |
| redis | 6379 | - | Cache |
| backend-1 | 8000 | - | FastAPI backend |
| backend-2 | 8000 | - | FastAPI backend |
| haproxy-client | 8080 | 8080 | Client-facing LB |

## Docker İmajları

| Servis | İmaj |
|---|---|
| patroni | Build (`postgres:16` + Python3 + Patroni[etcd] + etcd binary) |
| haproxy-db | Build (patroni imajı) |
| haproxy-client | `haproxy:lts` |
| etcd | `quay.io/coreos/etcd:v3.5.18` |
| redis | `redis:7-alpine` |
| backend | Build (`python:3.12-slim` + FastAPI) |

## Alınan Kararlar

| # | Konu | Karar |
|---|---|---|
| 1 | Health check EP | Write: `HEAD /primary`, Read: `HEAD /replica` (Patroni REST API, port 8008) |
| 2 | Item şeması | `id` (UUID), `name` (text), `created_at` (timestamp) |
| 3 | API endpoint'leri | `POST/GET /items`, `GET/DELETE /items/{id}` + `GET /health` |
| 4 | Cache stratejisi | Redis, key `item:{id}` / `items:all`, TTL 60s, bağlanamazsa DB'ye fallback |
| 5 | Patroni imajı | `FROM postgres:16` + Python3 + `pip install patroni[etcd]` + etcd binary |
| 6 | HAProxy config | Statik, 2 listen: port 5000 (primary) + port 5001 (replicas) |
| 7 | Port mapping (host) | 8080, 5000, 5001, 7000, 2379 |
| 8 | Data persistence | Yok — her sefer temiz başlangıç |
| 9 | Restart policy | `unless-stopped` her serviste |
| 10 | haproxy-client | `haproxy:lts`, mode http, `GET /health` |
| 11 | Chaos test | 0.5s interval, POST->GET->DELETE loop, süre değişken, başarı oranı + kesinti süresi |
| 12 | Dizin yapısı | `patroni/`, `haproxy/`, `backend/`, `tests/` |
| 13 | GitHub | Repo: `demirberkbesel/ha-system`, hata çıkarsa issue |
| 14 | Connection pool | write=3, read=5 |
| 15 | DB kullanıcısı | `postgres/postgres`, `postgres` veritabanı |
| 16 | Tablo motoru | SQLAlchemy, UUID primary key |
| 17 | Network | Tüm servisler `ha-net` bridge network'ünde |

## Faz 1 — DB Cluster (Patroni + etcd)

**Hedef**: etcd + 3 Patroni-Postgres node'unu ayağa kaldır.

**Dockerfile** (`patroni/Dockerfile`):
- Base: `postgres:16`
- Kurulum: Python3 + pip + `psycopg2-binary` + `patroni[etcd]`
- etcd binary: `v3.5.18` GitHub release'ten indir
- Config: `patroni.yml` (YAML, env var override)
- Entrypoint: `entrypoint.sh` (PATRONI_NAME, PATRONI_ETCD3_HOSTS, connect_address'leri set eder)

**Patroni YAML config** (`patroni/patroni.yml`):
- scope: ha-cluster
- restapi listen: 0.0.0.0:8008
- etcd3 hosts: etcd:2379
- pg_hba: local trust + host md5 + replicator replication
- max_connections: 100
- wal_level: replica, hot_standby: on

**Test**:
- `patronictl -c /etc/patroni.yml list` ile 1 leader + 2 replica doğrula
- Primary'i durdur (`docker compose stop postgres-1`), auto-failover'ı gözlemle
- Yeni primary otomatik seçilmeli, veri kaybı olmamalı

## Faz 2 — DB Load Balancer (haproxy-db, read/write split)

**Hedef**: HAProxy'de iki listen bloğu ile okuma/yazma ayrımı.

**HAProxy config** (`haproxy/haproxy-db.cfg`):
```
listen primary   -> port 5000, HEAD /primary   -> sadece primary 200 döner
listen replicas  -> port 5001, HEAD /replica   -> sadece replicalar 200 döner
```
- `check port 8008`: health check Patroni REST API'ye, trafik 5432'ye
- `inter 3s fall 3 rise 2`: 3 saniyede bir check, 3 başarısızlıkta down, 2 başarıda up
- `mode tcp`: PostgreSQL Layer 4

**Test**:
- Port 5000 her zaman primary'e gidiyor mu (`pg_is_in_recovery() = f`)
- Port 5001 sadece replicalara gidiyor mu, primary hiç girmiyor mu (`pg_is_in_recovery() = t`)
- Primary değiştiğinde write havuzu yeni primary'i takip ediyor mu

## Faz 3 — Backend + Cache

**Hedef**: FastAPI CRUD API + Redis cache-aside pattern.

**API Endpoint'leri**:
- `GET /health` — health check
- `POST /items` — item oluştur (write engine, cache invalidate)
- `GET /items` — tüm item'leri listele (cache-aside, read engine)
- `GET /items/{id}` — tek item getir (cache-aside, read engine)
- `DELETE /items/{id}` — item sil (write engine, cache temizle)

**Dual DB Engine** (`backend/db.py`):
- Write engine: `postgresql://postgres:postgres@haproxy-db:5000/postgres` (pool_size=3)
- Read engine: `postgresql://postgres:postgres@haproxy-db:5001/postgres` (pool_size=5)

**Cache** (`backend/cache.py`):
- Redis URL: `redis://redis:6379/0`
- TTL: 60 saniye
- Redis yoksa hata fırlatma, direkt DB'ye fallback yap
- `socket_connect_timeout=2, socket_timeout=2`

**Item Model** (`backend/models.py`):
- id: UUID primary key
- name: String
- created_at: DateTime (UTC)

## Faz 4 — Client Load Balancer (haproxy-client)

**Hedef**: Backend'ler arasında round-robin + health check.

**HAProxy config** (`haproxy/haproxy-client.cfg`):
```
listen api -> port 8080, mode http, GET /health
server backend-1 backend-1:8000
server backend-2 backend-2:8000
```

## Faz 5 — Unit + Integration Testler

**Unit testler** (`tests/test_unit.py`):
- Item model CRUD (SQLite in-memory)
- Cache fallback (Redis mock)
- Route validation (missing name, not found)

**Integration testler** (`tests/test_integration.py`):
- Gerçek sisteme karşı HTTP istekleri
- CRUD akışı, edge case'ler (404, 400)

## Faz 6 — Chaos / Dayanıklılık Testleri

**Chaos test script** (`tests/chaos_test.py`):
- Sürekli POST → GET → DELETE döngüsü
- 0.5 saniye interval
- Başarı oranı ve maksimum kesinti süresi raporlanır

**4 Test**:

| # | Test | İşlem | Beklenen |
|---|---|---|---|
| 1 | Backend failure | `docker compose stop backend-1` | backend-2 trafiği alır |
| 2 | Replica DB failure | `docker compose stop postgres-1` | Read havuzu diğer replicalarla devam eder |
| 3 | Primary DB failure | `docker compose stop postgres-2` (primary) | Auto-failover, write havuzu yeni primary'e yönelir |
| 4 | Cache failure | `docker compose stop redis` | DB'ye fallback, sistem çalışmaya devam eder |

## Faz 7 — Uçtan Uca Senaryo

1. Sistem ayağa kaldır, health check
2. 5 item oluştur
3. Tüm item'leri listele
4. Chaos tetikle (backend-1 durdur) + istek atmaya devam et
5. Backend-1'i geri getir
6. Item'leri temizle
7. DB'den doğrulama (hem write hem read havuzu)
8. Küme durumunu göster

## Komutlar

### Ortamı hazırla (ilk sefer)
```bash
python3 -m venv /tmp/testenv
/tmp/testenv/bin/pip install pytest requests sqlalchemy redis fastapi psycopg2-binary
```

### Sistem ayağa kaldır
```bash
docker compose down -v
docker compose build
docker compose up -d
sleep 30
```

### Unit testler
```bash
PYTHONPATH=$(pwd)/backend /tmp/testenv/bin/python -m pytest tests/test_unit.py -v
```

### Integration testler
```bash
/tmp/testenv/bin/python -m pytest tests/test_integration.py -v
```

### Chaos testleri
```bash
# Test 1: Backend failure
/tmp/testenv/bin/python tests/chaos_test.py http://localhost:8080 30 &
sleep 5 && docker compose stop backend-1 && wait
docker compose start backend-1

# Test 2: Replica failure
/tmp/testenv/bin/python tests/chaos_test.py http://localhost:8080 30 &
sleep 5 && docker compose stop postgres-1 && wait
docker compose start postgres-1

# Test 3: Primary failure
/tmp/testenv/bin/python tests/chaos_test.py http://localhost:8080 45 &
sleep 5 && docker compose stop postgres-2 && wait
docker compose start postgres-2

# Test 4: Redis failure
/tmp/testenv/bin/python tests/chaos_test.py http://localhost:8080 30 &
sleep 5 && docker compose stop redis && wait
docker compose start redis
```

### Küme durumu
```bash
docker exec ha-system-postgres-1-1 patronictl -c /etc/patroni.yml list
```

### API manuel test
```bash
curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/items -H "Content-Type: application/json" -d '{"name":"test"}'
curl -s http://localhost:8080/items
```

## Dizin Yapısı

```
ha-system/
├── docker-compose.yml
├── AGENTS.md
├── plan.md
├── pyproject.toml
├── .gitignore
├── patroni/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── patroni.yml
├── haproxy/
│   ├── haproxy-db.cfg
│   └── haproxy-client.cfg
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── db.py
│   ├── models.py
│   ├── cache.py
│   └── routes.py
└── tests/
    ├── test_unit.py
    ├── test_integration.py
    ├── chaos_test.py
    └── requirements-dev.txt
```
