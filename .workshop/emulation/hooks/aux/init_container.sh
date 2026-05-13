#!/bin/bash

set -Eeuo pipefail

if [ $(id -u) -ne 0 ]; then
  echo "Please run this script as root or using sudo!"
  exit 1
fi

# Container initialization script
# This script sets up the network and mosquitto broker when the container starts

# Network Setup - TAP interface configuration
TAP_IFACE="tap0"
HOST_IP="192.0.2.2"
DEVICE_IP="192.0.2.1"
SUBNET="192.0.2.0/24"

# Create TAP interface (delete if exists first)
ip link delete $TAP_IFACE 2>/dev/null || true
ip tuntap add name $TAP_IFACE mode tap

# Configure interface using the proven sequence from force_net.sh
ip link set $TAP_IFACE down
ip link set $TAP_IFACE up
ip addr flush dev $TAP_IFACE
ip addr add $HOST_IP/24 dev $TAP_IFACE

# Configure iptables
iptables -D INPUT -i $TAP_IFACE -j ACCEPT 2>/dev/null || true
iptables -A INPUT -i $TAP_IFACE -j ACCEPT

# Enable IP forwarding
sysctl -w net.ipv4.ip_forward=1 >/dev/null

# Mosquitto Setup

# Kill any existing mosquitto processes
pkill mosquitto 2>/dev/null || true
sleep 0.5

# Copy mosquitto configuration
cp /var/lib/workshop/sdk/emulation/sdk/hooks/aux/mosquitto_tap.conf /etc/mosquitto/mosquitto.conf

# Clean any persistence data
rm -rf /var/lib/mosquitto/* 2>/dev/null || true

# Start mosquitto service
mosquitto -c /etc/mosquitto/mosquitto.conf -d

# Wait for mosquitto to start
sleep 1

# Verify mosquitto is running
if pgrep -x mosquitto >/dev/null; then
  echo "Mosquitto broker started successfully on $HOST_IP:1883"
else
  echo "Warning: Mosquitto may not have started correctly"
fi
