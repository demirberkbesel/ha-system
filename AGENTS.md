# HA System Project

## Servis isimleri ve portlar

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

## Kurallar

- Tüm servisler `ha-net` bridge network'ünde
- Port numaraları ve servis isimleri sabit, değiştirilmemeli
- Docker imaj isimleri: `patroni` (build), `haproxy:lts`, `redis:7-alpine`, `quay.io/coreos/etcd:v3.5.18`
- Her fazdan sonra kullanıcıya onay sormadan ilerlenmez (kural: grilling sonrası tüm fazlar tek seferde yapılır)
- Hata durumunda GitHub issue açılır

## Fazlar

1. **DB cluster**: etcd + 3 Patroni-Postgres node
2. **DB LB**: haproxy-db (read/write split)
3. **Backend + Cache**: FastAPI CRUD + Redis cache-aside
4. **Client LB**: haproxy-client (backend round-robin)
5. **Testler**: pytest unit + integration
6. **Chaos**: 4 dayanıklılık testi
7. **E2E**: Uçtan uca senaryo

## Health check endpoint'leri

- Write havuzu (port 5000): `HEAD /primary`
- Read havuzu (port 5001): `HEAD /replica`
- Backend health: `GET /health`
