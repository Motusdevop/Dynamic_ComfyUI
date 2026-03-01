#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env file. Create it from .env.example first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${PROJECT_ROOT:-}" ]]; then
  echo "PROJECT_ROOT is required in .env"
  exit 1
fi

if [[ "$(cd "$PROJECT_ROOT" && pwd)" != "$ROOT_DIR" ]]; then
  echo "PROJECT_ROOT ($PROJECT_ROOT) must point to this repository path ($ROOT_DIR)."
  exit 1
fi

if [[ -z "${SERVER_PUBLIC_HOST:-}" ]]; then
  echo "SERVER_PUBLIC_HOST is required in .env"
  exit 1
fi

mkdir -p "$PROJECT_ROOT/data/shared_models" "$PROJECT_ROOT/data/users"

IMAGE_TAG="${COMFY_BASE_IMAGE:-dynamiccomfy/comfyui:cuda12.1}"

echo "Building ComfyUI base image: $IMAGE_TAG"
docker build -t "$IMAGE_TAG" -f comfy/Dockerfile .

echo "Starting API service"
docker compose up --build -d api

echo "Done. API health: http://127.0.0.1:${API_PORT:-8000}/health"
