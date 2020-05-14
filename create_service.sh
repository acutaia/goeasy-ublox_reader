#!/bin/bash
SYSTEMD_SCRIPT_DIR=$( cd  "$(dirname "${BASH_SOURCE:=$0}")" && pwd)
cp -f "$SYSTEMD_SCRIPT_DIR/ublox-reader.service" /lib/systemd/system
chown root:root /lib/systemd/system/ublox-reader.service

systemctl daemon-reload
systemctl enable ublox-reader.service