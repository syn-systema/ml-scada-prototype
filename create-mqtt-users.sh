#!/bin/bash
# Script to create MQTT users for the AI SCADA system

# Define the config directory
CONFIG_DIR="$(pwd)/config/mosquitto"

# Ensure clean start
rm -f "$CONFIG_DIR/passwd"

# Create password file with the admin user - note the -b flag for non-interactive mode
docker run --rm -v "$CONFIG_DIR:/mosquitto/config" \
    eclipse-mosquitto:2.0.15 \
    mosquitto_passwd -c -b /mosquitto/config/passwd scada-admin scada123

# Add other service users
docker run --rm -v "$CONFIG_DIR:/mosquitto/config" \
    eclipse-mosquitto:2.0.15 \
    mosquitto_passwd -b /mosquitto/config/passwd api-service api-service-password

docker run --rm -v "$CONFIG_DIR:/mosquitto/config" \
    eclipse-mosquitto:2.0.15 \
    mosquitto_passwd -b /mosquitto/config/passwd simulator simulator-password

docker run --rm -v "$CONFIG_DIR:/mosquitto/config" \
    eclipse-mosquitto:2.0.15 \
    mosquitto_passwd -b /mosquitto/config/passwd gnn-service gnn-service-password

docker run --rm -v "$CONFIG_DIR:/mosquitto/config" \
    eclipse-mosquitto:2.0.15 \
    mosquitto_passwd -b /mosquitto/config/passwd agent-service agent-service-password

docker run --rm -v "$CONFIG_DIR:/mosquitto/config" \
    eclipse-mosquitto:2.0.15 \
    mosquitto_passwd -b /mosquitto/config/passwd hmi-client hmi-client-password

docker run --rm -v "$CONFIG_DIR:/mosquitto/config" \
    eclipse-mosquitto:2.0.15 \
    mosquitto_passwd -b /mosquitto/config/passwd automl-service automl-service-password

echo "MQTT users created successfully in $CONFIG_DIR/passwd"
echo "To enable password authentication, update mosquitto.conf and restart the MQTT broker."
