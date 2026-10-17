#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DEPLOY="/tmp/zecro-frontend-deploy"

echo "==> Budowanie frontendu..."
cd "$ROOT_DIR/frontend"
npm run build

echo "==> Przygotowanie pakietu wdrożeniowego..."
rm -rf "$TMP_DEPLOY"
mkdir -p "$TMP_DEPLOY/.vercel"
cp "$ROOT_DIR/frontend/.vercel/project.json" "$TMP_DEPLOY/.vercel/project.json"
rsync -av --exclude node_modules --exclude dist "$ROOT_DIR/frontend" "$TMP_DEPLOY/"

echo "==> Wdrażanie zecro-frontend na Vercel (produkcja)..."
cd "$TMP_DEPLOY"
npx vercel --prod --yes

echo "==> Wdrożenie zakończone sukcesem na https://zecro.pl!"
