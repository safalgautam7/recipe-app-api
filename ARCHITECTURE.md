# How the System Works — Architecture & Component Interactions

This document explains how the pieces of this project fit together and how a request flows through them, from the URL in your browser all the way down to a row in PostgreSQL.

There are **four layers**:

```
                    PROXY LAYER                        APP LAYER                              DATA LAYER
   ┌─────────────────────────────┐   ┌──────────────────────────────┐   ┌──────────────────────────┐
   │          nginx              │   │          uWSGI + Django       │   │        PostgreSQL       │
   │  (reverse proxy / web      │   │                              │   │                          │
   │   server, port 8000)       │   │                              │   │                          │
   │                             │   │                              │   │                          │
   │  static files: /static/*    │   │  views.py (DRF)              │   │   User, Recipe, Tag,     │
   │  everything else:           │──▶│  serializers.py              │──▶│   Ingredient tables      │
   │  forward (uwsgi protocol)   │   │  core/models.py              │   │                          │
   └─────────────────────────────┘   └──────────────────────────────┘   └──────────────────────────┘
                                             │   ▲
                                             │   │  media files (uploads/)
                                             ▼   │
                                        /vol/web/media   (shared volume, mounted into nginx too)
```

> The whole stack runs as **three Docker containers** orchestrated by `docker-compose-deploy.yml`. They run inside one Docker network, and their names (`app`, `db`, `proxy`) act as DNS names — the containers find each other by name, not IP.

---

## 1. The components

| Component | Container | Base | Role | Exposed port |
| --------- | --------- | ---- | ---- | ------------ |
| **nginx** | `proxy` | `nginx-unprivileged` |  Receives every HTTP request, serves static files, proxies everything else to uWSGI. | `8000` (the only one visible to the outside world) |
| **uWSGI** | `app` | `python:3.10-alpine` | Runs the Django application. Implements the Web Server Gateway Interface Protocol that Django needs. | `9000` (internal only) |
| **Django + DRF** | `app` | (part of app image) | actual application: URL routing, views, serializers, models, admin, OpenAPI docs. | — |
| **PostgreSQL** | `db` | `postgres:16-alpine` | Stores all data permanently. | `5432` (internal only) |
| **Docker volumes** | — | — | Persistent storage that outlives containers (database + uploaded files/static). | — |

### What each process does

**nginx** (in `proxy/`):
- Listens on port 8000 (`LISTEN_PORT`).
- Serves anything under `/static` from `/vol/static` on disk (the collected static assets).
- For everything else, forwards the request to `app:9000` using the **uWSGI protocol** (`uwsgi_pass ${APP_HOST}:${APP_PORT}`), a binary protocol understood by uWSGI.
- Has `client_max_body_size 10M` — images larger than 10 MB are rejected here.

**uWSGI** (started by `scripts/run.sh`):
- Waits for the database with `python manage.py wait_for_db`.
- Runs `collectstatic`, applies `migrate`, then starts `uwsgi --socket :9000` with 2 workers.
- Talks the uwsgi protocol on socket `:9000`, which is exactly what nginx expects.

**Django** blocks:

| File | What it contains |
| ------ | ---------------- |
| `app/app/` (settings, urls, wsgi) | The Django project settings & root URL router. |
| `core/models.py` | `User` (email-based, custom manager), `Recipe`, `Tag`, `Ingredient` + their relationships. |
| `user/` | Auth endpoints: create user, get token, retrieve/update own profile. |
| `recipe/` | CRUD endpoints for recipes, tags, ingredients; view-sets + serializers; image upload. |
| `rest_framework.authtoken` | Issues a per-user token string for authentication. |

**PostgreSQL** holds the four tables (plus Django's own admin/auth/session tables) created by `migrations/`.

---

## 2. What happens when you request `GET /api/recipe/recipes/`

Here is step by step process:

1. **Your client** (curl, browser, Swagger UI) sends → `GET http://<vm-ip>:8000/api/recipe/recipes/`.
2. **nginx** accepts the connection on port 8000. The path doesn't start with `/static`, so it proxies with the uwsgi protocol to the `app` container (uWSGI on port 9000).
3. **uWSGI** hands the request to Django's WSGI handler (config `app/wsgi.py` → `app/urls.py`).
4. **Django URL resolver** matches `api/recipe/...` to `include("recipe.urls")`, and the DRF `DefaultRouter` matches the rest to `RecipeViewSet` and action `list`.
5. **DRF pipeline**:
   - **Authentication** (`TokenAuthentication`, set in `settings.REST_FRAMEWORK`): looks for the `Authorization: Token <token>` header, finds the `Token` row in the DB, attaches `request.user`.
   - **Permission** (`IsAuthenticated`): if no valid token → returns `401 {"detail": "Authentication credentials were not provided."}` and stops.
6. **View** → `RecipeViewSet.get_queryset()` filters `Recipe.objects.filter(user=request.user).order_by("-id")`; optional `tags` and `ingredients` query params filter too.
7. **Serializer** (`RecipeSerializer`) converts each `Recipe` row into JSON, including nested `tags` and `ingredients` lists.
8. The JSON is returned back up the same chain: DRF → Django → uWSGI → nginx → your client.

That single downward/upward path is the same for every endpoint; only the viewset and serializer change.

---

## 3. Networking and how containers find each other

Both Compose files create a **bridge network**. Compose assigns each service its container name as a hostname:

```yaml
# docker-compose-deploy.yml
services:
  app:
    environment:
      - DB_HOST=db        # Django connects to "db" by name
  proxy:
    # nginx forwards requests to app:9000 by name
```

- Django connects to the DB using `DB_HOST=db` - Compose DNS resolves `db` to the Postgres container's internal IP. No hard-coded IPs anywhere.
- nginx proxies to `app:9000` - resolves `app` to the uWSGI container.
- Postgres never appears outside the network: no `ports:` mapping. The only public entry point is nginx's port 8000.

---

## 4. Authentication flow: tokens and users

Custom `User` model (`core/models.py`) uses **email** as the username field:

```
create /api/user/create/   →  UserManager.create_user()    (hashes the password)
login  /api/user/token/     →  auth authtoken → a token string is stored in DB
manage /api/user/me/        →  RetrieveUpdate, returns your own profile
```

- Passwords are hashed by Django at `UserManager`; plain text never stored.
- Tokens are rows in the `authtoken_token` table; the token string is sent by the client and replaced with the user on every authenticated request.
- Viewsets use `TokenAuthentication` + `IsAuthenticated` (defined once in `settings.py` and applied per view).

```
curl -X POST /api/user/token/
   {email, password}
      │
      ▼
authenticate() → ok
      │
      ▼
authtoken issued → "token": "fee723..."  (stored in DB)
      │
      ▼
further requests → Authorization: Token fee723...  → request.user="deploy@example.com"
```

---

## 5. Static and media files

Two kinds of static files in Django have different producers/consumers:

**Static (CSS/JS/admin files)** - read-only code assets:

1. `python manage.py collectstatic` (run in `scripts/run.sh`) copies everything (Django admin CSS and DRF assets among them) into `STATIC_ROOT` (`/vol/web/static`).
2. nginx `location /static { alias /vol/static; }` serves them from the shared volume at high speed. No Django needed.

**Media (uploaded recipe images)** - user data:
1. Client sends a multipart `POST /api/recipe/recipes/<id>/upload-image/`; `RecipeImageSerializer` validates, `Pillow` saves the file under `/vol/web/media/uploads/recipe/<uuid>.jpg`.
2. Later requests for `/static/media/uploads/recipe/<uuid>.jpg` are served by nginx from the **same shared volume** (`static-data`), which is mounted in both `app` at `/vol/web` and `proxy` at `/vol/static` (they overlay the volume contents).

Why share a volume? Because in production Django literally cannot serve its own media over the socket - the web server must. By mounting the same volume in the app container (writes uploads) and the proxy (serves them) both sides see the same files.

In dev, Django can serve media itself: when `DEBUG=1`, `urls.py` appends `static(settings.MEDIA_URL, document_root=...)`.

---

## 6. Data persistence: Docker volumes

Volumes are how you keep data alive across container restarts and redeploys:

| Volume | Where in `docker-compose` | What it holds |
| --------- | ---------------------------------- | ------------------------------------------- |
| `dev-db-data` / `postgres-data` | mounted at `/var/lib/postgresql/data` in `db` | All database rows |
| `dev-static-data` / `static-data` | `app` at `/vol/web`, `proxy` at `/vol/static` | Collected static + uploaded recipe images |

When you `up -d --build` the `app` container after a code change, the container is destroyed and recreated, but the *volume keeps its files*, which is why your recipes, users and images survive. Only `docker compose down -v` deletes the data volumes.

---

## 7. Development vs production (dev/prod compose)

| Aspect | Dev (`docker-compose.yml`) | Production (`docker-compose-deploy.yml`) |
| -------- | -------------------------- | ------------------------------------------- |
| App server | Django's own `runserver` (port 8000, `--reload`) | uWSGI with 2 workers, serving on socket `:9000` |
| Reverse proxy | none (Django served directly) | nginx in front on port 8000 |
| DEBUG | `DEBUG=1` | `DEBUG` not set, so it defaults to `0` |
| Code updates | `./app` is mounted live → edit and reload | Code is copied into the image at build time → must rebuild |
| DB | Postgres 16 the same | Postgres 16 the same |
| Secrets | hard-coded dev values (`devuser`/`changeme`) | values injected from `.env` via `--env-file` |

The **Dockerfile** builds one image for both. The `DEV=true` build arg appends `requirements.dev.txt` (flake8) to dev images, so prod images are leaner.

---

## 8. Your build process (how an image is created)

`Dockerfile` steps:
1. base `python:3.10-alpine`
2. copies requirements + scripts
3. `apk add` build deps (Postgres headers for psycopg2, jpeg/libjpeg for Pillow) and `pip install -r requirements.txt`
4. deletes build deps (keep the image small)
5. `COPY ./app /app`
6. creates a non-root user `django-user`, creates `/vol/web` dirs
7. default command `run.sh` (start the stack: wait for DB → collectstatic → migrate → uWSGI)

Each `up -d --build` creates:
- images from `Dockerfile` (app) and `proxy/Dockerfile`
- containers for `app`, `db`, `proxy`
- network: one internal network
- volumes: postgres + static

This image then, at runtime, uses the `/scripts/run.sh` on the container `CMD`.

---

## 9. CI (GitHub Actions)

`.github/workflows/checks.yml` runs on every `git push`:

1. Checkout the repository.
2. Install the Compose binary.
3. (Logging into Docker Hub — currently no consumer.)
4. Run tests inside a container: `docker compose run --rm app sh -c "python manage.py wait_for_db && python manage.py test"`.
5. Run lint: `docker compose run --rm app sh -c "flake8"`.

The tests produce coverage for `core` (models, admin, commands) and the APIs (`user`, `recipe`), including image-upload and authentication tests, all inside the same images that production uses.

---

## 10. A quick mental model

```
 something changes          recipe created         app restarted
     │                           │                       │
     ▼                           ▼                       ▼
 build once                 rows written             volume keeps
 (image)                    to postgres              the database
     │                           │                       │
     ▼                           ▼                       ▼
  nginx:8000  ──▶  uWSGI:9000  ──▶  Django  ──▶  PostgreSQL
```

**Four invariants to remember:**
1. Everything public goes through nginx (port 8000). No other port is exposed.
2. All dynamic traffic ends at Django, which ends in Postgres.
3. Containers are temporary; volumes are permanent.
4. Code changes don't apply until you rebuild the image (production) - redeploy via `up -d --build [service]`.