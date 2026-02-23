#!/bin/sh
set -e

CERT_DIR="/etc/nginx/certs"
CERT_FILE="$CERT_DIR/cert.pem"
KEY_FILE="$CERT_DIR/key.pem"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "[InfraScope] SSL certificates not found — generating self-signed..."
    mkdir -p "$CERT_DIR"
    apk add --no-cache openssl > /dev/null 2>&1 || true
    openssl req -x509 -nodes -days 3650 \
        -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/CN=infrascope.local" \
        -addext "subjectAltName=DNS:infrascope.local,DNS:localhost,IP:127.0.0.1" \
        2>/dev/null
    echo "[InfraScope] Self-signed certificate created. For trusted HTTPS use mkcert."
fi

exec nginx -g "daemon off;"
