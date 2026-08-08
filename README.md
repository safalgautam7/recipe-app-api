# Recipe App API

A production-oriented Django REST Framework (DRF) backend for managing recipes, tags, and ingredients, with token-based authentication, image uploads, OpenAPI documentation, and a full Docker/nginx deployment setup.

## Features

- **Custom user model** (`email` instead of `username`) with password hashing, staff/superuser flags, and a Django admin UI.
- **Recipe management** — full CRUD for recipes (`title`, `description`, `time_minutes`, `price`, `link`, `tags`, `ingredients`, `image`).
- **Tags & ingredients** — user-scoped reusable attributes with `assigned_only` filtering.
- **Recipe filtering** — by comma-separated tag IDs and ingredient IDs.
- **Image upload** — per-recipe image upload stored under `uploads/recipe/` with a unique UUID filename.
- **Token authentication** (`rest_framework.authtoken`) required for all data endpoints.
- **Interactive API docs** — OpenAPI schema + Swagger UI (`drf-spectacular`).
- **Dockerized** — dev compose with auto-reload and `postgres:16`; production compose with uWSGI + nginx reverse proxy serving static/media.
- **CI** — GitHub Actions runs the test suite and `flake8` lint inside the Docker containers.
- **Django admin** for users, recipes, tags, and ingredients.

## Tech Stack

| Layer       | Technology                                             |
| ----------- | ------------------------------------------------------ |
| Language    | Python 3.10 (Alpine 3.21)                              |
| Framework   | Django 4.2 / Django REST Framework                     |
| Database    | PostgreSQL 16                                          |
| API docs    | drf-spectacular (Swagger UI)                           |
| App server  | uWSGI (production), Django `runserver` (dev)          |
| Web server  | nginx (unprivileged, reverse proxy)                    |
| Container   | Docker + docker-compose v2                             |
| CI          | GitHub Actions (`flake8` + Django tests)                |
| Extra tools | Pillow (images), custom `wait_for_db` management command |

## Project Structure

```
recipe-app-api/
├── app/                        # Django project root
│   ├── app/                    # Project configuration
│   │   ├── settings.py         # Django settings (env-driven)
│   │   ├── urls.py             # Root URL configuration
│   │   ├── wsgi.py / asgi.py   # Server entry points
│   │   └── calc.py             # Small utility module (from the platform tutorial)
│   ├── core/                   # Shared models, admin, custom commands
│   │   ├── models.py           # User, Recipe, Tag, Ingredient
│   │   ├── admin.py            # Django admin customization
│   │   ├── migrations/         # 0001..0005
│   │   ├── management/
│   │   │   └── commands/
│   │   │       ├── wait_for_db.py   # Polls DB until available
│   │   │       └── test.py          # Wraps test (waits for DB first)
│   │   └── tests/              # model/admin/command tests
│   ├── user/                   # Auth API
│   │   ├── views.py            # CreateUserView, CreateTokenView, ManageUserView
│   │   ├── serializers.py      # UserSerializer, AuthTokenSerializer
│   │   ├── urls.py
│   │   └── tests/
│   ├── recipe/                 # Recipe/tag/ingredient APIs
│   │   ├── views.py            # RecipeViewSet, TagViewSet, IngredientViewSet
│   │   ├── serializers.py
│   │   ├── urls.py             # DRF DefaultRouter
│   │   └── tests/
│   └── manage.py
├── proxy/                      # Production reverse proxy
│   ├── Dockerfile              # nginx-unprivileged
│   ├── default.conf.tpl        # nginx conf template (envsubst)
│   ├── run.sh                  # Render config then start nginx
│   └── uwsgi_params
├── scripts/
│   └── run.sh                  # prod startup: wait_for_db → collectstatic → migrate → uwsgi
├── Dockerfile                  # Python image with venv + optional dev deps
├── docker-compose.yml           # Development stack
├── docker-compose-deploy.yml   # Production stack (app + db + proxy)
├── requirements.txt            # Runtime dependencies
├── requirements.dev.txt        # Lint-only deps (flake8)
└── .github/workflows/checks.yml# CI: Docker install → login → test → lint
```

## Requirements

- Docker (with Compose v2) — recommended; everything runs in containers.
- No local Python install required.

## Getting Started (Development)

```bash
git clone https://github.com/<you>/recipe-app-api.git
cd recipe-app-api

# copy the env template (compose uses its own dev env vars, but keep for reference)
cp .env.sample .env

docker compose up --build
```

The API will be available at `http://127.0.0.1:8000/`:

- Swagger docs: `http://127.0.0.1:8000/api/docs/`
- OpenAPI schema: `http://127.0.0.1:8000/api/schema/`
- Django admin: `http://127.0.0.1:8000/admin/`

The dev compose file mounts `./app` into the container and sets `DEBUG=1`, so code changes auto-reload. PostgreSQL runs in a sibling `db` container (dev credentials: `devdb` / `devuser` / `changeme`).

### Running tests & lint

```bash
docker compose run --rm app sh -c "python manage.py test && flake8"
```

## API Reference

All data endpoints require `Authorization: Token <your-token>`.

### User & auth

| Method | URL                       | Description                        |
| ------ | ------------------------- | ---------------------------------- |
| POST   | `/api/user/create/`       | Register a user                     |
| POST   | `/api/user/token/`       | Obtain an auth token                |
| GET    | `/api/user/me/`           | Get the authenticated user profile |
| PATCH  | `/api/user/me/`           | Update own profile                  |

Example — get a token:

```bash
curl -X POST http://127.0.0.1:8000/api/user/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "testpass123"}'
```

### Recipes

| Method | URL                                   | Description            |
| ------ | ------------------------------------- | ---------------------- |
| GET    | `/api/recipe/recipes/`                | List my recipes (filters)      |
| POST   | `/api/recipe/recipes/`                | Create a recipe         |
| GET    | `/api/recipe/recipes/<id>/`          | Retrieve a recipe       |
| PUT/PATCH | `/api/recipe/recipes/<id>/`        | Update a recipe         |
| DELETE | `/api/recipe/recipes/<id>/`          | Delete a recipe         |
| POST   | `/api/recipe/recipes/<id>/upload-image/` | Upload a recipe image (multipart) |

Recipe payload fields: `title`, `description`, `time_minutes`, `price`, `link`, `tags` (`[{"name": ...}]`), `ingredients` (`[{"name": ...}]`), `image`.

Nested tags/ingredients are automatically created (or reused) and assigned to the authenticated user.

**Supported query params** (`GET /api/recipe/recipes/`):

- `?tags=1,2` — return only recipes that have these tag IDs
- `?ingredients=1,2` — return only recipes that have these ingredient IDs

### Tags & ingredients

| Method             | URL                          | Description                         |
| ------------------ | ---------------------------- | ----------------------------------- |
| GET / POST         | `/api/recipe/tags/`            | List / create tags                  |
| PUT/PATCH/DELETE   | `/api/recipe/tags/<id>/`      | Update / delete a tag               |
| GET / POST         | `/api/recipe/ingredients/`     | List / create ingredients           |
| PUT/PATCH/DELETE   | `/api/recipe/ingredients/<id>/`| Update / delete an ingredient       |

**Supported query params** (for tags / ingredients):

- `?assigned_only=1` — return only items attached to at least one recipe

### Generate your token and try it

```bash
curl -X POST http://127.0.0.1:8000/api/recipe/recipes/ \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Spaghetti", "time_minutes": 25, "price": "12.99"}'
```

Full machine-readable API is always available at `/api/schema/` and documented in the Swagger UI at `/api/docs/`.

## Configuration

All settings are read from environment variables (see `app/app/settings.py`):

| Variable         | Dev default | Description                                    |
| ---------------- | ----------- | ---------------------------------------------- |
| `DB_HOST`       | `db`        | PostgreSQL host                                  |
| `DB_NAME`       | `devdb`     | Database name                                   |
| `DB_USER`       | `devuser`   | Database user                                   |
| `DB_PASS`       | `changeme`  | Database password                               |
| `SECRET_KEY`    | `changeme`  | **Must be a long random value in production.** |
| `ALLOWED_HOSTS`  | ``          | Comma-separated list of allowed hostnames        |
| `DEBUG`          | `0`         | `1` enables Django debug + media serving in dev    |

## Deployment (Production)

The repo ships a `docker-compose-deploy.yml` used for the production stack: application is served by **uWSGI**, static files are collected and served by an **nginx** reverse-proxy container, and PostgreSQL lives in a named volume.

```bash
# 1. Create a secure env file (never commit it)
cp .env.sample .env
# Fill in real values:
#   DB_NAME, DB_USER, DB_PASS (strong passwords)
#   DJANGO_SECRET_KEY      (e.g. python -c "import secrets; print(secrets.token_urlsafe(50))")
#   DJANGO_ALLOWED_HOSTS   (your domain or server IP, comma separated)

# 2. Run the deploy stack
docker compose -f docker-compose-deploy.yml --env-file .env up --build -d

# 3. Check logs
docker compose -f docker-compose-deploy.yml --env-file .env logs -f app
```

The startup script (`scripts/run.sh`) automatically waits for the database, runs `collectstatic`, applies `migrate`, and starts uWSGI workers. nginx serves the app on host port `8000` and proxies to uWSGI on the internal `app:9000` socket.

## CI / CD

`.github/workflows/checks.yml` runs on every push:

1. Installs Docker Compose.
2. Logs into Docker Hub (from repo secrets `DOCKERHUB_USER` / `DOCKERHUB_TOKEN`).
3. Runs the Django test suite inside the app container.
4. Runs `flake8` lint inside the app container.

Add the `DOCKERHUB_USER` / `DOCKERHUB_TOKEN` secrets to your GitHub repo for the workflow to succeed.

## Deployment readiness notes

The project is **deployable as-is** (CI + tests + compose + proxy all present). Before you point a real domain at it, close these gaps:

1. **Force a strong secret key** — remove the `changeme` `SECRET_KEY` default, or fail startup when unset in production.
2. **Enable CORS if a browser frontend calls the API** — `django-cors-headers` is installed but not registered in `INSTALLED_APPS` / `MIDDLEWARE`, so the API currently business as-is. Add `CORS_ALLOWED_ORIGINS`.
3. **Pin dependencies** — `requirements.txt` uses unbounded versions and ships `black` into the runtime image; pin versions and move `black` to `requirements.dev.txt`.
4. **Terminate TLS** — at an upper load balancer or add SSL to the nginx `proxy/default.conf.tpl`.
5. **Publish app images** — the CI logs into Docker Hub but never pushes; for reproducible deployments, publish a tagged image and reference it from the deploy compose.
6. **Harden /api-for-pub** — consider DRF throttling for `/api/user/token/` and `SECURE_*` settings for production.

## License

See your project's license (if any).