# Bookstore Microservices

Учебный пример микросервисной архитектуры на Python (FastAPI + PostgreSQL + RabbitMQ + Redis + gRPC). Реализует требования по DDD, распределённым транзакциям, transaction outbox/inbox, JWT-аутентификации и CI/CD.

## Структура

```
bookstore/
├── docker-compose.yml
├── .env.example
├── .gitlab-ci.yml
├── db/init/                 # SQL-скрипты инициализации БД и сид
├── proto/catalog.proto      # общий контракт gRPC
├── shared/auth.py           # общий модуль JWT
├── services/
│   ├── identity/            # порт 8001
│   ├── catalog/             # порт 8002 + gRPC 50051
│   ├── sales/               # порт 8003
│   └── inventory/           # порт 8004
└── tests/e2e/               # сквозной тест саги
```

### Архитектура

4 микросервиса, одна PostgreSQL-БД с отдельными схемами под каждый ограниченный контекст:

| Сервис | Схема БД | HTTP | gRPC | Роль |
|---|---|---|---|---|
| **identity** | `identity` | 8001 | — | Регистрация, логин, выпуск JWT |
| **catalog** | `catalog` | 8002 | 50051 | Каталог книг, отзывы, справочники |
| **sales** | `sales` | 8003 | — | Заказы, gRPC-клиент в catalog, outbox/inbox |
| **inventory** | `inventory` | 8004 | — | Остатки, закупки, consumer, outbox/inbox |

### Распределённая транзакция (choreography saga)

```
1. POST /orders → Sales
2. Sales → gRPC GetBooksByIds(Catalog) — получить цены
3. Sales: Order(PENDING) + outbox sales.order.created
4. Outbox publisher → RabbitMQ
5. Inventory: читает sales.order.created (inbox — идемпотентность)
   ├─ достаточно остатков → outbox inventory.stock.reserved
   └─ недостаточно → outbox inventory.stock.rejected
6. Outbox publisher Inventory → RabbitMQ
7. Sales: читает inventory.stock.* (inbox — идемпотентность)
   ├─ reserved → Order CONFIRMED
   └─ rejected → Order CANCELLED
```

## Демонстрация требований

| Требование | Где смотреть |
|---|---|
| **1–2. DDD-объекты и контексты** | структура `services/*/src/domain`, `application`, `infrastructure`, `presentation` |
| **3. Микросервисы + REST + чистая архитектура** | `services/*/src/` — каждый сервис по слоям |
| **4. Docker Compose** | `docker-compose.yml` |
| **5. Redis-кеш** | `services/catalog/src/infrastructure/cache.py`; в UI: `GET /books` дважды, `redis-cli keys "catalog:*"` |
| **6. PostgreSQL** | `db/init/*.sql` — схемы по контекстам |
| **7. Распределённая транзакция (saga)** | `services/sales/src/application/use_cases.py` (`CreateOrder`, `HandleInventoryResult`) + `services/inventory/src/application/use_cases.py` (`HandleOrderCreated`) |
| **8. Outbox / Inbox** | `services/*/src/infrastructure/outbox_publisher.py`, `services/*/src/infrastructure/consumer.py` |
| **9. RabbitMQ** | `services/*/src/infrastructure/rabbit.py`, `docker-compose.yml` (порт 15672) |
| **10. gRPC** | `proto/catalog.proto`, `services/catalog/src/infrastructure/grpc_service.py`, `services/sales/src/infrastructure/grpc_client.py` |
| **11. JWT** | `services/identity/src/infrastructure/security.py`, `shared/auth.py` |
| **12. Тесты** | `services/*/tests/unit/`, `tests/e2e/test_saga.py` |
| **13. GitLab CI** | `.gitlab-ci.yml` |
| **14. Deploy** | `.gitlab-ci.yml` → `deploy:staging` (пока что заглушка) |

## Запуск

Требуется установленный Docker Desktop.

```powershell
# 1. Скопировать переменные окружения
cp .env.example .env

# 2. Собрать и поднять всё
docker compose up -d --build

# 3. Подождать 20–30 секунд, пока сервисы стартуют
# 4. Проверить health
curl.exe -s http://localhost:8001/health
curl.exe -s http://localhost:8002/health
curl.exe -s http://localhost:8003/health
curl.exe -s http://localhost:8004/health
```

### Точки входа

- Identity Swagger: http://localhost:8001/docs
- Catalog Swagger: http://localhost:8002/docs
- Sales Swagger: http://localhost:8003/docs
- Inventory Swagger: http://localhost:8004/docs
- RabbitMQ Management UI: http://localhost:15672 (guest/guest)

### Учётные записи

Сид выполняется автоматически при первом старте.

| Email | Пароль | Роль |
|---|---|---|
| admin@bookstore.com | admin123 | admin |
| olga.sosnovskaya@mail.ru | password123 | customer (id=1) |
| ... (всего 14 клиентов с префиксом из сида) | password123 | customer |

**Важно:** админ не может оформлять заказы (его нет в `sales.customers`). Для демонстрации заказов используйте клиентский аккаунт.

## Как прогнать тесты локально

```powershell
# Unit-тесты любого сервиса (без БД)
cd services/sales && pytest tests/unit -v

# E2E-тесты (требуют поднятого стека)
docker compose up -d --build
$env:RUN_E2E = "1"
pytest tests/e2e -v
```

> Локальные тесты запускаются в venv: в requirements зафиксированы pytest 8.3.3 и pytest-asyncio 0.24.0. Глобальный pytest 9 несовместим с этой связкой.

## Остановка

```powershell
# Остановить всё, сохранить данные
docker compose down

# Остановить и очистить БД (например, перед повторным сидом)
docker compose down -v
```
