#!/usr/bin/env bash
# Deploys a given commit of dcfrqb/vpn-site on the app server.
# Called by deploy/hook/deployer.py (GitHub Actions webhook) or by hand: deploy.sh <sha>
set -euo pipefail

APP_DIR=/opt/vpn-site
SHA="${1:?usage: deploy.sh <commit sha>}"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "bad sha"; exit 2; }

exec 9>/var/lock/vpn-site-deploy.lock
flock -n 9 || { echo "another deploy is running"; exit 3; }

cd "$APP_DIR"
git fetch --quiet origin main
git merge-base --is-ancestor "$SHA" origin/main || { echo "sha is not on origin/main"; exit 4; }
git checkout --quiet --detach "$SHA"

free_gb=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
(( free_gb >= 5 )) || { echo "only ${free_gb}G free on /, aborting"; exit 5; }

export GIT_SHA="$SHA"
docker compose build --pull
docker compose up -d --remove-orphans

for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8040/api/health" | grep -q "\"version\":\"$SHA\""; then
    curl -fsS -o /dev/null "http://127.0.0.1:3040/" && { echo "deployed $SHA"; break; }
  fi
  (( i == 30 )) && { echo "health check failed"; docker compose ps; exit 6; }
  sleep 4
done

docker image prune -f >/dev/null
docker builder prune -f --filter until=72h >/dev/null
