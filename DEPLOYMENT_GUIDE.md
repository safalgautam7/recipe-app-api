# Deployment Guide for Starters

This guide walks you step by step from **installing Multipass** all the way to **deploying the Django Recipe API** in a production-like configuration on a free local virtual machine: creating the VM, installing Docker, moving your code over, managing secrets with a `.env` file, launching the stack, redeploying a code change, setting up a firewall, exposing the API publicly via a Cloudflare Tunnel, and cleaning up when you are done.

Everything in this guide is free. The core deployment runs on your own computer. Sections 14-15 walk you through making it reachable from anywhere on the internet for free.

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
- [14. Firewall with ufw](#14-firewall-with-ufw)
- [15. Public access via Cloudflare Tunnel](#15-public-access-via-cloudflare-tunnel)
- [16. After a restart](#16-after-a-restart)

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
| **Image** | A blueprint | A frozen, read-only template containing Python + your code + dependencies. Built once. |
| **Container** | A *running* instance of an image, isolated from everything else. |

You build **images** once, then Compose creates **containers** from them. In this project Docker Compose creates three containers: `app` (your Django code + uWSGI), `db` (PostgreSQL), and `proxy` (nginx). All three live in the same VM and talk to each other over an internal Docker network.

---

## 4. Create a virtual machine

Launch the VM with this single command:

```bash
multipass launch 24.04 --name recipe-vm --cpus 2 --memory 2G --disk 10G
```

What each part means:

- `24.04` - the OS image to use: Ubuntu 24.04 LTS
- `--name recipe-vm` - name of vm
- `--cpus 2` - allocates 2 CPU cores
- `--memory 2G` - allocates 2 GB of RAM
- `--disk 10G` - allocates 10 GB of disk

The first launch downloads the Ubuntu image, so it takes a minute or two. Verify:

```bash
multipass list
```

You should see `recipe-vm` with a state of `Running` and an IP address like `10.198.x.y`. That IP is private, only your computer can reach the VM, which is exactly what we want for a sandbox.

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

- `docker.io` - the Docker engine
- `docker-compose-v2` - the compose plugin (for `docker compose` commands)

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

### Option A: mount your project folder (recommended for learning)

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

Look at `app/app/settings.py`, configuration is read from environment variables instead of being written in code:

```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'changeme')
DEBUG = bool(int(os.environ.get('DEBUG', 0)))
ALLOWED_HOSTS = [] + [h for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h]
```

If you are cloning the repo, you get *defaults* (`changeme`, `DEBUG=0`, empty hosts) - never your real secrets. You supply the real values at deployment time.

### use of .env

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

Create it **inside the VM**, in the `ubuntu` home directory, never in your git checkout.
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
| Cloudflare tunnel URL changed after restart | Quick tunnels generate a new random URL every time | Grab the new URL from `/tmp/tunnel.log`, update `DJANGO_ALLOWED_HOSTS`, and redeploy |
| `400 Bad Request` over the public URL | The tunnel hostname is not in `ALLOWED_HOSTS` | Add the hostname to your env file and redeploy |

---

## 14. Firewall with ufw

**ufw** (Uncomplicated Firewall) is Ubuntu's built-in firewall. It controls which ports are allowed to receive traffic from the outside.

### Why you need it

Even if your VM is on a private IP, a firewall is part of good server hygiene. The rule is simple: **deny everything inbound by default, then open only what you need**.

### Enable it safely

> **Critical:** always allow SSH (`OpenSSH`) *before* enabling ufw. If you forget, ufw will drop the SSH connection and you lose access to the VM permanently — Multipass cannot reconnect.

```bash
multipass exec recipe-vm -- sudo ufw allow OpenSSH
multipass exec recipe-vm -- sudo ufw default deny incoming
multipass exec recipe-vm -- sudo ufw --force enable
```

Check the rules:

```bash
multipass exec recipe-vm -- sudo ufw status
```

You should see:

```
Status: active

To                         Action      From
--                         ------      ----
OpenSSH                    ALLOW       Anywhere
OpenSSH (v6)               ALLOW       Anywhere (v6)
```

### Do I need to open port 8000?

**No** — and here is why: a Cloudflare Tunnel (section 15) uses an *outbound* connection from your VM to Cloudflare's edge. The firewall only governs *inbound* traffic. Since traffic arrives through a tunnel that the VM itself initiated, ufw does not interfere. You do not need any `8000` rule.

If you ever run without a tunnel (e.g. local-only or port-forwarding), you would add:

```bash
multipass exec recipe-vm -- sudo ufw allow 8000/tcp
```

But with a tunnel in place, keep it deny-all-inbound.

---

## 15. Public access via Cloudflare Tunnel

A **Cloudflare quick tunnel** (`trycloudflare.com`) lets you expose a local service to the public internet for free, with no account, no domain, and no credit card. It works by establishing an *outbound* connection from your VM to Cloudflare's edge — meaning you don't need to open any inbound firewall ports.

### Install cloudflared

```bash
multipass exec recipe-vm -- bash -c \
  "curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
  -o /tmp/cloudflared && sudo mv /tmp/cloudflared /usr/local/bin/cloudflared \
  && sudo chmod +x /usr/local/bin/cloudflared"
```

Verify:

```bash
multipass exec recipe-vm -- cloudflared --version
```

### Start the tunnel in tmux

We use **tmux** so the tunnel keeps running after the command finishes. Install tmux and start a detached session:

```bash
multipass exec recipe-vm -- bash -c \
  "sudo apt-get install -y -qq tmux >/dev/null && \
  tmux new-session -d -s tunnel 'cloudflared tunnel --url http://localhost:8000 > /tmp/tunnel.log 2>&1'"
```

Wait a few seconds, then grab the public URL:

```bash
multipass exec recipe-vm -- grep -o 'https://.*\.trycloudflare\.com' /tmp/tunnel.log
```

It will print something like:

```
https://coast-maintains-pty-launched.trycloudflare.com
```

> **Note:** the URL is random and changes every time the tunnel restarts.

### Update ALLOWED_HOSTS

Django rejects requests from hostnames not in `ALLOWED_HOSTS`. Add your tunnel hostname:

```bash
multipass exec recipe-vm -- bash -c \
  "sed -i 's/^DJANGO_ALLOWED_HOSTS=.*/DJANGO_ALLOWED_HOSTS=10.198.x.x,localhost,127.0.0.1,<YOUR-TUNNEL-HOSTNAME>/' /home/ubuntu/recipe.env"
```

Replace `<YOUR-TUNNEL-HOSTNAME>` with the URL you just grabbed.

### Redeploy the app

```bash
multipass exec recipe-vm -- bash -c \
  "cd /opt/recipe-app && docker compose -f docker-compose-deploy.yml \
  --env-file /home/ubuntu/recipe.env up -d --build app"
```

### Verify from the public URL

Open the Swagger docs in your browser (or use curl):

```
https://<YOUR-TUNNEL-HOSTNAME>/api/docs/
```

You should see the interactive Swagger UI. Try creating a user and a recipe — the full API works over the public internet.

### What you just built

```
friend's phone (any network)
       |
       v
 Cloudflare edge (HTTPS)
       |
       v
 your VM's cloudflared (outbound tunnel)
       |
       v
 nginx :8000 → uWSGI :9000 → Django → PostgreSQL
```

No inbound ports opened. ufw stays deny-all. The tunnel is the only door, and it was opened from the inside.

---

## 16. After a restart

When you `multipass stop recipe-vm` and later `multipass start recipe-vm`, two things happen:

1. **Docker containers auto-restart** — because all services have `restart: always` in `docker-compose-deploy.yml`, Docker restarts `app`, `db`, and `proxy` automatically when the VM boots.

2. **The Cloudflare tunnel URL changes** — the quick tunnel gives a new random URL each time it starts.

### Restart checklist

```bash
# 1. start the VM
multipass start recipe-vm

# 2. start a new tunnel (the old tmux session may be dead)
multipass exec recipe-vm -- bash -c \
  "tmux new-session -d -s tunnel 'cloudflared tunnel --url http://localhost:8000 > /tmp/tunnel.log 2>&1'"

# 3. wait a few seconds, then grab the NEW URL
multipass exec recipe-vm -- grep -o 'https://.*\.trycloudflare\.com' /tmp/tunnel.log

# 4. update ALLOWED_HOSTS with the new hostname
multipass exec recipe-vm -- bash -c \
  "sed -i 's/^DJANGO_ALLOWED_HOSTS=.*/DJANGO_ALLOWED_HOSTS=10.198.x.x,localhost,127.0.0.1,<NEW-HOSTNAME>/' /home/ubuntu/recipe.env"

# 5. redeploy
multipass exec recipe-vm -- bash -c \
  "cd /opt/recipe-app && docker compose -f docker-compose-deploy.yml \
  --env-file /home/ubuntu/recipe.env up -d --build app"

# 6. verify
multipass exec recipe-vm -- curl -s http://localhost:8000/api/health/
```

### Check that Docker came back up

```bash
multipass exec recipe-vm -- bash -c \
  "cd /opt/recipe-app && docker compose -f docker-compose-deploy.yml ps"
```

All three containers should say `Up`. If the `app` container is restarting repeatedly, check logs:

```bash
multipass exec recipe-vm -- bash -c \
  "cd /opt/recipe-app && docker compose -f docker-compose-deploy.yml logs --tail=20 app"
```

### Why the URL changes

Quick tunnels (`trycloudflare.com`) are designed for temporary demos. Each time `cloudflared tunnel --url` starts, Cloudflare assigns a fresh subdomain. This is free and instant but not permanent. For a **permanent** URL, you would need either:

- A **Cloudflare named tunnel** with a domain you own, or
- A **Tailscale Funnel** (`https://vm.tailnet.ts.net`) which gives a stable hostname with a free account.

For a demo or exam, the quick tunnel URL works perfectly — just update `ALLOWED_HOSTS` and redeploy after every restart.

---

## Quick reference

```bash
# Build + start production
docker compose -f docker-compose-deploy.yml --env-file /home/ubuntu/recipe.env up -d --build

# Rebuild only after a code change
docker compose -f docker-compose-deploy.yml --env-file /home/ubuntu/recipe.env up -d --build app

# Follow logs (live)
docker compose -f docker-compose-deploy.yml logs -f app

# --- Firewall ---
sudo ufw allow OpenSSH          # ALWAYS do this first
sudo ufw default deny incoming
sudo ufw --force enable
sudo ufw status                 # verify

# --- Cloudflare Tunnel ---
# Install
curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /tmp/cloudflared
sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Start tunnel (in tmux so it survives)
tmux new-session -d -s tunnel 'cloudflared tunnel --url http://localhost:8000 > /tmp/tunnel.log 2>&1'

# Grab the public URL
grep -o 'https://.*\.trycloudflare\.com' /tmp/tunnel.log

# Update ALLOWED_HOSTS and redeploy
sed -i 's/^DJANGO_ALLOWED_HOSTS=.*/DJANGO_ALLOWED_HOSTS=<IP>,localhost,127.0.0.1,<TUNNEL_HOSTNAME>/' /home/ubuntu/recipe.env
docker compose -f docker-compose-deploy.yml --env-file /home/ubuntu/recipe.env up -d --build app

# --- After a restart ---
multipass start recipe-vm
tmux new-session -d -s tunnel 'cloudflared tunnel --url http://localhost:8000 > /tmp/tunnel.log 2>&1'
grep -o 'https://.*\.trycloudflare\.com' /tmp/tunnel.log
# update ALLOWED_HOSTS with new hostname, then redeploy

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