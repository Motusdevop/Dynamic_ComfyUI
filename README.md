# DynamicComfy

MVP orchestration service for ComfyUI Docker instances.

## Server deployment

1. Install Docker Engine + Docker Compose plugin on the server.
2. Copy project to server, for example into `/opt/dynamiccomfy`.
3. Open project directory and create env file:

```bash
cp .env.example .env
```

4. Edit `.env`:
`SERVER_PUBLIC_HOST` must be your public IP or domain.
`JWT_SECRET` must be replaced with a strong random value.
`ENABLE_GPU=true` only when NVIDIA runtime is configured on the server.
5. Run bootstrap:

```bash
./scripts/bootstrap_server.sh
```

6. Create first user:

```bash
docker compose run --rm api uv run python -m scripts.seed_user <username> <password>
```

7. Check API:

```bash
curl http://127.0.0.1:${API_PORT:-8000}/health
```

## Update on server

```bash
git pull
./scripts/bootstrap_server.sh
```

## Files added for deployment

- `.env.example`: production configuration template.
- `scripts/bootstrap_server.sh`: one-shot build and startup script.
- `comfy/Dockerfile`: base ComfyUI image used for per-user instances.
