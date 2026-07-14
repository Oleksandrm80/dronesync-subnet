#!/bin/bash
set -e

echo "=== DroneSync Deploy ==="

# Копируем systemd сервис
cp /root/dronesync-subnet/deploy/dronesync.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable dronesync
systemctl restart dronesync

# Устанавливаем nginx
apt-get install -y nginx

# Копируем конфиг nginx
cp /root/dronesync-subnet/deploy/nginx.conf /etc/nginx/sites-available/dronesync
ln -sf /etc/nginx/sites-available/dronesync /etc/nginx/sites-enabled/dronesync
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "=== Done ==="
echo "API: http://128.140.52.200"
systemctl status dronesync --no-pager
