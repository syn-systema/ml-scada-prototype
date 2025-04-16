FROM frangoteam/fuxa:latest

# Copy the configuration file
COPY fuxa-config.json /app/data/fuxa-config.json

# Expose the port
EXPOSE 1881

# Set environment variables
ENV FUXA_HOST=0.0.0.0
ENV FUXA_PORT=1881
ENV FUXA_MQTT_URL=mqtt://mqtt-broker:1883
ENV FUXA_MQTT_USERNAME=dashboard
ENV FUXA_MQTT_PASSWORD=dashboard-password

# Set the working directory
WORKDIR /app

# Start Fuxa
CMD ["node", "server.js"]
