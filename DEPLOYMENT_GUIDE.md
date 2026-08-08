# Deployment Guide for Beginners

This guide walks you step by step from **installing Multipass** all the way to **deploying the Django Recipe API** in a production-like configuration on a free local virtual machine: creating the VM, installing Docker, moving your code over, managing secrets with a `.env` file, launching the stack, redeploying a code change, and cleaning up when you are done.

Everything here is free and runs on your own computer. Nothing is exposed to the public internet.

---

## Table of contents

- [1. What is Multipass, and how this works](#1-what-is-multipass-and-how-this-works)
- [2. Install Multipass](#2-install-multipass)
- [3. Key concepts: VM, container, image](#3-key-concepts-vm-container-image)
- [4. Create a virtual machine](#4-create-a-virtual-machine)
- [5. Talk to the VM](#5-talk-to-the-vm)
- [6. Install Docker inside the VM](#6-install-docker-inside-the-vm)
- [7. Get your code into the VM](#7-get-your-code-into-the-vm)
- [8. Secrets and the `.env` file](#8-secrets-and-the-env-file)
- [9. Build and start the production stack](#9-build-and-start-the-production-stack)
- [10. Verify the API is running](#10-verify-the-api-is-running)
- [11. Deploying a new code change](#11-deploying-a-new-code-change)
- [12. Stop, start and delete the VM](#12-stop-start-and-delete-the-vm)
- [13. Troubleshooting](#13-troubleshooting)

---

## 1. What is Multipass, and how this works

**Multipass** is an official Canonical tool that creates and manages Ubuntu **virtual machines (VMs)** on your computer. It is free, runs on Linux, macOS and Windows, and gives you a whole Ubuntu computer without buying or renting anything.

We use it to simulate a "production server" that only you can see. Inside that VM we run the same three pieces your cloud setup would have:

- **Django app + uWSGI** – the application itself. uWSGI is the server that *runs* Django.
- **PostgreSQL** – the database where users, recipes, tags and ingredients are stored.
- **nginx** – a web server out the front. It receives every request and forwards them to uWSGI, and it serves the static files.

The flow looks like this:

```
Your browser / curl
        |
        v
     nginx          (port 8000, front door)
        |
        v
     uWSGI + Django  (internal port 9000)
        |
        v
     PostgreSQL      (internal port 5432)
```

---

## 2. Install Multipass

### On Ubuntu / Debian (recommended)

```bash
sudo snap install multipass
```

Check it installed:

```bash
multipass --version
multipass list   # empty list is fine, you have no VMs yet
```

### On macOS / Windows

Download the installer from the official site: https://multipass.io

Run it, then open a terminal and check `multipass --version` works.

---

## 3. Key concepts: VM, container, image

Three similar-sounding things, three different levels:

| Concept | Analogy              | What it is                                                                     |
| ------- | -------------------- | ------------------------------------------------------------------------------- |
| **VM**  | A computer inside your computer | A whole Ubuntu machine (own CPU, memory, disk, IP) running on your laptop. |
| **Image** | A cooking recipe / blueprint | A frozen, read-only template containing Python + your code + dependencies. Built once. |
| **Container** | The dish you cook | A *running* instance of an image, isolated from everything else. |

You build **images** once, then Compose creates **containers** from them. In this project Docker Compose creates three containers: `app` (your Django code + uWSGI), `db` (PostgreSQL), and `proxy` (nginx). All three live in the same VM and talk to each other over an internal Docker network.

---

## 4. Create a virtual machine

Launch the VM with this single command:

```bash
multipass launch 24.04 --name recipe-vm --cpus 2 --memory 2G --disk 10G
```

What each part means:

- `24.04` – the OS image to use: Ubuntu 24.04 LTS
- `--name recipe-vm` – what we call the VM
- `--cpus 2` – give it 2 CPU cores
- `--memory 2G` – give it 2 GB of RAM
- `--disk 10G` – give it 10 GB of disk

The first launch downloads the Ubuntu image, so it takes a minute or two. Verify:

```bash
multipass list
```

You should see `recipe-vm` with a state of `Running` and an IP address like `10.198.x.y`. That IP is private — only your computer can reach the VM, which is exactly what we want for a sandbox.

---

## 5. Talk to the VM

Two ways to run commands on the VM, both from your own terminal on your own machine.

**1. Interactive shell** (works like SSH, no keys needed):

```bash
multipass shell recipe-vm
```

Your prompt changes to something like `ubuntu@recipe-vm:~$`. Type `exit` to leave.

**2. Single command without entering a shell:**

```bash
multipass exec recipe-vm -- python3 --version
```

`multipass exec <vm> -- <command>` runs a command inside the VM and returns the output. The rest of this guide uses this form so you can run commands without switching shells.

---

## 6. Install Docker inside the VM

Docker is not installed in a fresh Ubuntu VM, so we install two packages:

- `docker.io` – the Docker engine
- `docker-compose-v2` – the compose plugin (for `docker compose` commands)

```bash
multipass exec recipe-vm -- sudo bash -c \
  "apt-get update && apt-get install -y docker.io docker-compose-v2"
```

Make Docker start on boot and add your user to the `docker` group (so you don't need `sudo` for every docker command):

```bash
multipass exec recipe-vm -- sudo systemctl enable --now docker
multipass exec recipe-vm -- sudo usermod -aG docker ubuntu
```

> The `usermod` change only takes effect in *new* sessions. For simplicity, the commands below use `sudo docker compose ...`, which works no matter what session is being used.

Verify:

```bash
multipass exec recipe-vm -- docker --version
multipass exec recipe-vm -- docker compose version
```

---

## 7. Get your code into the VM

There are three common ways. For learning, start with the **mount** approach.

### Option A — mount your project folder (recommended for learning)

This makes your local folder appear inside the VM and it *stays live*: when you edit a file on your laptop, the VM sees the change immediately. No SSH or copying needed.

```bash
multipass mount /home/you/path/to/recipe-app-api recipe-vm:/opt/recipe-app
```

Check it appears:

```bash
multipass exec recipe-vm -- ls /opt/recipe-app
```

### Option B — copy the folder once

```bash
multipass transfer /home/you/path/to/recipe-app-api recipe-vm:/opt/recipe-app
```

Useful if you don't want a live link. Remember to re-transfer after you change code.

### Option C — git clone (closest to real production)

If your code is on GitHub, clone it inside the VM:

```bash
multipass exec recipe-vm -- git clone https://github.com/you/recipe-app-api.git /opt/recipe-app
```

Then your loop is exactly what a real deployment does: change code locally, `git push`, then on the server `git pull` and rebuild.

---

## 8. Secrets and the `.env` file

### Why environment variables exist

Look at `app/app/settings.py` — configuration is read from environment variables instead of being written in code:

```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'changeme')
DEBUG = bool(int(os.environ.get('DEBUG', 0)))
ALLOWED_HOSTS = [] + [h for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h]
```

If someone clones your repo, they get *defaults* (`changeme`, `DEBUG=0`, empty hosts) — never your real secrets. You supply the real values at deployment time.

### What a `.env` file is

Docker Compose can inject variables from a file. In `docker-compose-deploy.yml` you will see placeholders like:

```yaml
environment:
  - SECRET_KEY=${DJANGO_SECRET_KEY}
  - ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS}
```

At deploy time, when you pass `--env-file`, Compose replaces the `${...}` placeholders with the values from the file:

```
DB_NAME=recipe
DB_USER=recipe
DB_PASS=recipe-pass-2026
DJANGO_SECRET_KEY=<a long random string>
DJANGO_ALLOWED_HOSTS=192.168.1.100
```

### Creating the env file in the VM

Create it **inside the VM**, in the `ubuntu` home directory — never in your git checkout. The repo's `.gitignore` already ignores `.env`, and committing secrets is a serious security mistake.

```bash
multipass exec recipe-vm -- bash -c "cat > /home/ubuntu/recipe.env <<'EOF'
DB_NAME=recipe
DB_USER=recipe
DB_PASS=recipe-pass-2026
DJANGO_SECRET_KEY=REPLACE_WITH_A_LONG_RANDOM_STRING
DJANGO_ALLOWED_HOSTS=192.168.1.100
EOF"
```

Set tight permissions so only your user can read it:

```bash
multipass exec recipe-vm -- chmod 600 /home/ubuntu/recipe.env
```

### Generate a real secret key

Never leave `changeme` in production. Generate a long random string:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Paste the output as the `DJANGO_SECRET_KEY` value in the env file.

### What each variable does

| Variable                  | Purpose                                                                                                            |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `DB_NAME` / `DB_USER` / `DB_PASS` | Credentials used by the `db` container (as `POSTGRES_*`) and by Django to connect to it. |
| `DJANGO_SECRET_KEY`       | Django signs cookies/sessions with it. Must be secret and unique per deployment.                                    |
| `DJANGO_ALLOWED_HOSTS`    | Comma-separated list of hosts (IPs/domains) allowed to talk to the app. The VM's IP must be on this list.          |

To *rotate* the secret later: edit the file, then redeploy the full stack (section 11).

---

## 9. Build and start the production stack

From your host terminal:

```bash
multipass exec recipe-vm -- bash -c \
  "cd /opt/recipe-app && docker compose -f docker-compose-deploy.yml --env-file /home/ubuntu/recipe.env up -d --build"
```

Decode this one-liner:

| Bit | What it does |
| ---- | --------------------------------------------------- |
| `cd /opt/recipe-app` | change to the mounted project inside the VM |
| `docker compose` | use Compose, the multi-container orchestrator |
| `-f docker-compose-deploy.yml` | use *this* compose file (production, not dev) |
| `--env-file /home/ubuntu/recipe.env` | inject the secrets we made |
| `up` | create and start containers |
| `-d` | detached (run in the background) |
| `--build` | build the images first |

The first build downloads base images and installs Python packages, so give it a few minutes. When it finishes, check the result:

```bash
multipass exec recipe-vm -- bash -c \
  "cd /opt/recipe-app && docker compose -f docker-compose-deploy.yml ps"
```

You should see three containers `Up`:

- `recipe-app-app-1` – Django + uWSGI
- `recipe-app-db-1` – PostgreSQL
- `recipe-app-proxy-1` – nginx (on port 8000)

---

## 10. Verify the API is running

From your own terminal (not inside the VM), hit the VM's IP on port 8000. First get the IP:

```bash
multipass list   # note the IPv4 column for recipe-vm
```

Then, replacing `<VM-IP>`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://<VM-IP>:8000/api/schema/    # expect 200
curl -s -o /dev/null -w "%{http_code}\n" http://<VM-IP>:8000/api/docs/      # expect 200
curl -s -o /dev/null -w "%{http_code}\n" http://<VM-IP>:8000/api/recipe/recipes/  # expect 401
```

- `/api/schema/` → `200` (OpenAPI schema)
- `/api/docs/` → `200` (Swagger UI)
- `/api/recipe/recipes/` → `401` (auth required, correct)

Also confirm nginx serves static files:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "http://<VM-IP>:8000/static/static/admin/css/base.css"   # expect 200
```

### Full end-to-end test: create user → login → create a recipe

```bash
BASE=http://<VM-IP>:8000

# 1. create a user
curl -X POST $BASE/api/user/create/ -H "Content-Type: application/json" \
  -d '{"email":"deploy@example.com","password":"testpass123","name":"Deploy Test"}'

# 2. get an auth token
TOKEN=$(curl -X POST $BASE/api/user/token/ -H "Content-Type: application/json" \
  -d '{"email":"deploy@example.com","password":"testpass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 3. create a recipe
curl -X POST $BASE/api/recipe/recipes/ -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Pasta","time_minutes":20,"price":"9.99","tags":[{"name":"Italian"}]}'

# 4. list recipes
curl $BASE/api/recipe/recipes/ -H "Authorization: Token $TOKEN"
```

If you get `201 Created` for the user and recipe, the whole chain nginx → uWSGI → Django → Postgres works.

---

## 11. Deploying a new code change

In production the code is **copied into the image at build time** (`COPY ./app /app` in the Dockerfile), and the running container does **NOT** hot-reload. That's the key difference from development: dev compose mounts `./app` into the container and auto-reloads; production requires a rebuild.

So every code change looks like this:

**Step 1 — change the code**

Edit a Django file on your laptop. For a classic first experiment, add a `/api/health/` endpoint to `app/app/urls.py`:

```python
from django.http import JsonResponse

def health(request):
    return JsonResponse({"status": "ok", "version": "1"})

# and in urlpatterns:
path("api/health/", health, name="health"),
```

- With the **mount** you're done — the file is already updated in the VM.
- With **git clone**, commit/push, then `git pull` inside the VM.

**Step 2. Rebuild only the app container**

```bash
multipass exec recipe-vm -- bash -c \
  "cd /opt/recipe-app && docker compose -f docker-compose-deploy.yml --env-file /home/ubuntu/recipe.env up -d --build app"
```

**Step 3. Verify the change took effect**

```bash
curl http://<VM-IP>:8000/api/health/
# before the rebuild you get 404; after you get: {"status": "ok", "version": "1"}
```

**Important facts to remember:**

- Your **database survives redeploys** — it lives in a named Docker volume (`postgres-data`), not in the app container. You can prove it: create a recipe, rebuild the app, and the recipe is still listed.
- If you changed a **secret** or any env variable, rebuild the **whole** stack (`up -d --build`, no service name), because all containers need the new environment.
- The `proxy` container usually does **not** need rebuilding — unless you changed the nginx config itself.

---

## 12. Stop, start and delete your VM

| You want to | Command | Explanation |
| ------------ | ------------------------------------------------------ | ------------- |
| Take the VM offline but keep everything | `docker compose -f docker-compose-deploy.yml down` then `multipass stop recipe-vm` | Removes containers (data volumes stay). VM freezes, using no CPU. |
| Bring it back up | `multipass start recipe-vm` then `cd /opt/recipe-app && docker ... up -d` | Compose services have `restart: always`, so after booting the VM Docker restarts them automatically. |
| Remove machine only (30-day grace) | `multipass delete recipe-vm && multipass purge` | Purge frees the disk immediately. |
| Remove **everything including the database** | Inside VM: `docker compose -f docker-compose-deploy.yml down -v` then Multipass delete/purge | The `-v` flag deletes the data volumes, so your database is wiped. Only use this when you want to start over. |

> `down -v` deletes the database volume. Your recipes will be gone forever. For normal stops use `down` alone.

---

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---------| ---------|-----|
| `Cannot connect to the Docker daemon` | Docker not running, or user not in `docker` group | `sudo systemctl status docker`; `sudo usermod -aG docker ubuntu` + log out/in |
| App logs keep saying "Waiting for database..." | Postgres wasn't up yet | It retries forever — wait. Check `docker compose ... logs db`. |
| Curl returns 401 on `/api/recipe/...` | You forgot the token | That IS expected. Get a token (section 10) and send `Authorization: Token ...` |
| Curl gets connection refused | Wrong IP, or the proxy container isn't running | Re-check `multipass list` — the IP can change across restarts. Use the current IP and confirm `docker compose ps` shows the proxy `Up`. |
| Nothing happens after editing code | You must rebuild the image | Run `up -d --build app`; a live edit alone doesn't affect a running container |
| Port 8000 already in use on the host | Another app uses it | Change the `ports: 8000:8000` mapping in `docker-compose-deploy.yml` to `8001:8000` |

---

## Quick reference

```bash
# Build + start production
docker compose -f docker-compose-deploy.yml --env-file /home/ubuntu/recipe.env up -d --build

# Rebuild only after a code change
docker compose -f docker-compose-deploy.yml --env-file /home/ubuntu/recipe.env up -d --build app

# Follow logs (live)
docker compose -f docker-compose-deploy.yml logs -f app

# Stop the stack but keep data + VM
docker compose -f docker-compose-deploy.yml down
multipass stop recipe-vm

# Resume later
multipass start recipe-vm
docker compose -f docker-compose-deploy.yml --env-file /home/ubuntu/recipe.env up -d

# Delete the VM + all data
multipass delete recipe-vm && multipass purge
```

You are now a rancher of a real three-container production stack. Everything in this guide is free and reversible — experiment freely.