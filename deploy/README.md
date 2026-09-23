# Deploy: vpn-site на app-сервере

Сервер: `crs-projects-fr-2` (HostVDS, адрес в servers.md). На нем же живут бот, budget-tracker, smeta, langlab, healthchecks и др.
Правило: сайт не трогает чужие контейнеры, сети, порты и базы.

## Что занято сайтом

| Что | Значение |
|---|---|
| Каталог | `/opt/vpn-site` |
| Compose-проект | `vpn-site` (сеть `vpn-site_default`) |
| Фронт | `127.0.0.1:3040` |
| API | `127.0.0.1:8040` |
| БД | свой контейнер `vpn-site-db`, порт наружу не публикуется |
| Домен | `vpn.crs-projects.com`, nginx vhost `deploy/nginx/vpn.crs-projects.com.conf`, сертификат certbot |
| Доступ к стенду | basic auth, файл `/etc/nginx/.htpasswd-vpn-site` |

Порты, занятые другими проектами на 23.09.2026: 3002, 3010, 3021, 3030, 5432, 6379, 8000, 8001, 8010, 8030, 8031, 8081, 8090, 8787.

## Ограничения

- Каждому контейнеру `mem_limit` и `cpus`: сайт не должен отбирать память у бота.
- К базе бота (`crs_vpn_db`) сайт напрямую не ходит. После релиза бота 3.0: только через API бота.
- Старая заготовка `/opt/site` (март 2026) не запущена, не трогаем до решения владельца.
- Перед `docker build`: `df -h /`. После выката: `docker image prune -f && docker builder prune -f`.
