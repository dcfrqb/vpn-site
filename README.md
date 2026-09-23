# vpn-site

Сайт CRS VPN: лендинг, личный кабинет, оплата, админка.

- Дизайн: принципы в `docs/design-principles.md`, макет в `design/mockup_v1.html`.
- Стенд: https://vpn.crs-projects.com (закрыт паролем).
- Деплой и изоляция на сервере: `deploy/README.md`.

## Структура

```
web/      фронтенд (Next.js)
api/      бэкенд (FastAPI)
deploy/   nginx, compose, скрипты выката
design/   макеты
docs/     заметки и решения
```

Репозиторий публичный: секреты, `.env`, дампы и ключи сюда не попадают.
