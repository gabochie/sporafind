#!/usr/bin/env bash
set -euo pipefail

# Deploy Sporafind API to Koyeb
# Prerequisites:
#   1. Koyeb CLI installed: curl -fsSL https://app.koyeb.com/install | sh
#   2. Authenticated: koyeb login
#   3. .env file at backend/.env with:
#        DATABASE_URL=postgresql+asyncpg://...
#        COMPANIES_HOUSE_API_KEY=...
#        SECRET_KEY=your-secret-here

echo "==> Loading environment variables..."
source "$(dirname "$0")/.env"

echo "==> Deploying to Koyeb..."
koyeb app create sporafind-api 2>/dev/null || true

koyeb service create sporafind-api \
  --app sporafind-api \
  --docker . \
  --ports 8080:http \
  --routes /:8080 \
  --env "DATABASE_URL=${DATABASE_URL}" \
  --env "COMPANIES_HOUSE_API_KEY=${COMPANIES_HOUSE_API_KEY}" \
  --env "SECRET_KEY=${SECRET_KEY}" \
  --env "ENVIRONMENT=production" \
  --regions fra \
  --instance-type free \
  --min-instances 1 \
  --max-instances 1 \
  --health-check-path /health

echo ""
echo "==> Deploying... check status with:"
echo "    koyeb service get sporafind-api --app sporafind-api"
echo ""
echo "==> Your API will be live at:"
echo "    https://sporafind-api.koyeb.app"
