#!/bin/sh
set -e

# Default API URL if not provided
API_URL="${BACKEND_API_URL:-http://localhost:8000}"

echo "Configuring frontend with Backend API URL: $API_URL"

# Create runtime config file
cat > /usr/share/nginx/html/config.js <<EOF
window.ENV = {
  BACKEND_API_URL: '$API_URL'
};
EOF

echo "Runtime configuration created successfully"

# Execute the CMD
exec "$@"
