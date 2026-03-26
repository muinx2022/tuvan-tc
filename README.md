# tuvan-tc (monorepo)

Django REST Framework backend compatible with the existing PostgreSQL schema and API from the Spring Boot project, plus `admin/` (Vite/React) and `web/` (Next.js) frontends.

## Layout

- `backend/` — Django project (`manage.py`, `config/`, `apps/`, `common/`)
- `admin/` — Admin UI (copied from the Java monorepo)
- `web/` — Web app (copied from the Java monorepo)
- `docker-compose.yml` — Postgres + Django + web + admin

## Setup

1. Create a virtualenv and install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and adjust `DATABASE_URL` if needed.

3. Ensure PostgreSQL has the **Flyway schema** (database `mvpdb`, user `mvp` / `mvp` by default).

   If the database is **empty**, apply the Spring migrations **in numeric order** (not alphabetical — `V10` must run after `V9`):

   ```powershell
   # From repo root, with Docker Postgres container `mvp-postgres` running:
   .\scripts\apply-flyway-sql.ps1
   ```

   Or set `FLYWAY_SQL_DIR` to your `backend/src/main/resources/db/migration` folder from the Java project.

4. Django `migrate` (only `auth` / `contenttypes`; app tables come from Flyway SQL above), then seed RBAC + admin:

```bash
cd backend
python manage.py migrate
python manage.py seed
```

5. Run the API:

```bash
cd backend
python manage.py runserver 0.0.0.0:8080
```

API base: `http://localhost:8080/api/v1`

## Run Everything From Root

From the repo root:

```bash
npm run dev
```

This runs `backend`, `web`, `admin`, and `t0-worker` in the same terminal. Use `Ctrl+C` to stop all of them.

To run the DNSE T0 worker separately from the repo root:

```bash
npm run dev:t0-worker
```

## Docker

```bash
docker compose up --build
```

Backend: port `8080`. Set `DATABASE_URL` if not using the bundled Postgres service.

## Notes

- JWT claims and `ApiResponse` envelope match the Spring Boot API for frontend compatibility.
- BCrypt passwords from Spring are verified with the `bcrypt` package.
