#!/usr/bin/env bash
# Cache-bust every script/style URL in the static site (run before each publish).
set -euo pipefail
V=$(date +%H%M%S)
cd "$(dirname "$0")/../web"
sed -i '' -E "s#(css/style\.css|js/app\.js|js/motion\.js)\?v=[0-9]+#\1?v=$V#g" index.html
sed -i '' -E "s#\./(reducer|replay|i18n)\.js\?v=[0-9]+#./\1.js?v=$V#g" js/app.js
echo "web assets version $V"
