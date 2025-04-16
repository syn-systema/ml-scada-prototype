MQTT Data Processing Troubleshooting Summary
Objective
The primary goal of this troubleshooting session was to resolve an issue where sensor data was not being received and processed by the data-api-service for storage in TimescaleDB. The problem stemmed from a mismatch in MQTT topic structures between the pipeline-simulator (which publishes sensor data) and the data-api-service (which subscribes to and processes this data).

Problem Identification
Initially, we identified that the data-api-service was not receiving any messages from the pipeline-simulator. By reviewing the logs of both services, we confirmed that pipeline-simulator was actively publishing data, but data-api-service showed no indication of incoming messages. Upon inspecting the code in data-api-service, specifically in main.py and mqtt_handler.py, we discovered that the service was subscribed to the topic sensors/# and was programmed to process messages only if the topic started with sensors/. Meanwhile, pipeline-simulator was publishing to a different topic structure, ai_scada/data/{sensor_id}.

This mismatch in topic naming conventions was the root cause of the communication failure between the two services. The data-api-service was listening on an outdated topic that did not align with what pipeline-simulator was using, resulting in no data being received or processed.

Steps Taken to Resolve the Issue
To address this issue, we followed a systematic approach to align the topic structures and ensure proper data flow:

Code Review and Update:
We first examined the subscription logic in main.py of data-api-service. The MQTT client was subscribing to sensors/#, which did not match the publishing topic from pipeline-simulator.
We updated the subscription topic in main.py to ai_scada/data/# to match the topic structure used by pipeline-simulator.
Additionally, in the on_message function within main.py, we modified the condition to check for topics starting with ai_scada/data/ instead of sensors/ before processing the message.
In mqtt_handler.py, we revised the process_sensor_data method to parse the topic format ai_scada/data/{sensor_id} instead of sensors/{sensor_id}. This included updating how the sensor ID was extracted from the topic and how confirmation messages were published back to ai_scada/data/{sensor_id}/confirmation.
Service Rebuild and Restart:
After making these code changes, we rebuilt the Docker image for data-api-service using the command docker compose build data-api-service to incorporate the updated code.
We then restarted the container with docker compose up -d data-api-service to apply the changes and ensure the service was running with the new topic configuration.
Initial Log Check:
Post-restart, we checked the logs of data-api-service using docker compose logs --tail 20 data-api-service to confirm it was subscribed to ai_scada/data/#. However, the logs still did not show any incoming messages being processed, which suggested that either the messages were not being received or they were not being logged at the current logging level.
Enhanced Logging for Debugging:
To gain deeper insight into the message processing, we updated the logging level in main.py from INFO to DEBUG. This change was intended to capture more detailed information about incoming messages and processing steps that might not be visible at the INFO level.
We again rebuilt and restarted the data-api-service to apply this logging change.
Final Log Verification:
After the second restart with DEBUG logging enabled, we reviewed the logs using docker compose logs --tail 50 data-api-service. This time, the logs clearly showed that data-api-service was receiving messages on topics like ai_scada/data/pressure-1, ai_scada/data/flow-1, etc. The logs detailed the receipt of sensor data, storage in the database, and publication of confirmation messages back to the respective confirmation topics.
Why We Took These Steps
Topic Alignment: Updating the subscription and processing logic in data-api-service to match pipeline-simulator's publishing topic was crucial because MQTT communication relies on exact topic matches for publishers and subscribers to exchange data. Without this alignment, messages published by pipeline-simulator would never reach data-api-service, resulting in a complete breakdown of the data pipeline.
Service Restart: Rebuilding and restarting the service after code changes ensured that the updated logic was loaded into the running container. Docker containers operate based on the image they are built from, so any code change necessitates a rebuild and restart to take effect.
Logging Enhancement: Initially, even after updating the topic, the logs did not show message processing, which could have been due to the logging level not capturing detailed enough information. By switching to DEBUG level, we ensured that every step of message receipt and processing was logged, allowing us to confirm whether the issue was resolved or if further investigation was needed.
Verification: Checking logs at each stage was essential to validate our changes. Without log verification, we could not confirm if the topic update was successful or if messages were being processed as expected. This step-by-step verification helped us pinpoint that the issue was resolved once detailed logging was enabled.
Outcome
The troubleshooting process successfully resolved the issue. With the topic structure updated to ai_scada/data/# in data-api-service and detailed logging enabled, we confirmed that sensor data from pipeline-simulator was being received, processed, and stored. Confirmation messages were also being published back, indicating a fully functional MQTT data flow between the services.

This resolution ensures that sensor data can now be properly stored in TimescaleDB, fulfilling the core objective of the data pipeline in the AI-SCADA system. If further verification is needed to confirm data storage in the database, a direct query to TimescaleDB could be the next step. However, based on the logs, the communication issue between pipeline-simulator and data-api-service has been fully addressed.

Lets Query the TimescaleDB to confirm the data is stored.

farseer@ai-stratagens:~/ai-scada$ docker compose exec tsdb psql -U scada -d scada_timeseries -c "SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 10;"
WARN[0000] /home/farseer/ai-scada/docker-compose.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion 
  id   |   sensor_id    |         timestamp          | value | quality 
-------+----------------+----------------------------+-------+---------
 15509 | pressure-1     | 2025-04-15 04:14:10.844309 | 35.35 |     100
 15510 | flow-1         | 2025-04-15 04:14:10.844309 | 48.07 |     100
 15511 | temp-1         | 2025-04-15 04:14:10.844309 |  68.9 |     100
 15512 | pressure-2     | 2025-04-15 04:14:10.844309 | 29.28 |     100
 15513 | flow-2         | 2025-04-15 04:14:10.844309 | 36.45 |     100
 15514 | vibration-1    | 2025-04-15 04:14:10.844309 |  2.92 |     100
 15515 | pressure-3     | 2025-04-15 04:14:10.844309 | 23.77 |     100
 15516 | flow-3         | 2025-04-15 04:14:10.844309 | 43.17 |     100
 15517 | temp-2         | 2025-04-15 04:14:10.844309 |  68.3 |     100
 15518 | oil-production | 2025-04-15 04:14:10.844309 | 75.83 |     100
(10 rows)

Summary of What We Built
We've built and deployed a streamlined AI SCADA (Supervisory Control and Data Acquisition) System as a rapidly deployable prototype for time series predictive analytics and maintenance. Using Docker containers, this system simulates, monitors, analyzes, and visualizes pipeline data. It integrates essential components to collect sensor data, store it, analyze it with machine learning for predictions, and provide a user interface for monitoring. Here's a breakdown of the key additions and configurations we've made during our session:

Nginx Reverse Proxy for FUXA HMI: We added an Nginx container as a reverse proxy to securely expose the FUXA HMI (Human-Machine Interface) to external users (e.g., your coworkers). This proxy now includes basic authentication to prevent unauthorized access.
Troubleshooting and Configuration: We resolved connectivity issues between services (e.g., data-api-service to TimescaleDB and MQTT broker), ensuring data flows correctly through the system. We also restarted services like automl-service to confirm functionality.
Documentation: We created a detailed deployment guide (deployment-guide.md) to streamline future setups of this system from scratch.
Connection to Current System Components
The AI SCADA system is composed of core interconnected components tailored for rapid deployment and testing. Below, I detail how the elements we worked on integrate with the essential system components as defined in your docker-compose.yml:

MQTT Broker (mqtt-broker)
Role: Acts as the central message hub for real-time data communication using the MQTT protocol.
Connections:
Receives data from pipeline-simulator (simulated sensor data published to topics like ai_scada/data/<sensor_id>).
Forwards data to data-api-service (subscribed to ai_scada/data/# for storage).
Sends and receives data to/from automl-service (publishes predictions to ai_scada/predictions/<sensor_id>).
Connects to fuxa (FUXA HMI subscribes to MQTT topics for real-time visualization of sensor data and predictions).
Our Work: We ensured all services could connect to the MQTT broker by verifying configurations and restarting services as needed.
TimescaleDB (tsdb)
Role: A time-series database for storing historical sensor data.
Connections:
Receives data from data-api-service (which processes MQTT messages and stores them in TimescaleDB).
Provides data to automl-service (fetches historical data for training machine learning models).
Accessible via pgadmin (a UI for database management and querying).
Our Work: We confirmed tsdb was operational and resolved connection issues with data-api-service, ensuring data storage. We also provided connection details for pgadmin.
Data API Service (data-api-service)
Role: Bridges MQTT data to persistent storage in TimescaleDB.
Connections:
Subscribes to MQTT topics (ai_scada/data/#) via mqtt-broker.
Writes data to tsdb.
Our Work: We restarted this service to fix connection issues with both MQTT and TimescaleDB, confirming in logs that it successfully processes and stores sensor data.
Pipeline Simulator (pipeline-simulator)
Role: Simulates sensor data for 17 different sensors (e.g., pressure, flow, temperature) every 5 seconds.
Connections:
Publishes data to mqtt-broker on topics like ai_scada/data/pressure-1.
Our Work: We verified through logs that it was actively publishing data, which was a key step in troubleshooting the data flow.
AutoML Service (automl-service)
Role: Uses machine learning (H2O AutoML) to analyze historical data and predict future sensor values.
Connections:
Fetches historical data from tsdb (directly or via data-api-service).
Publishes predictions to mqtt-broker on topics like ai_scada/predictions/pressure-1.
Exposes H2O Flow UI for model visualization (http://localhost:54321).
Our Work: We restarted this service after fixing data-api-service to ensure it could fetch data and train models, confirming through logs that predictions are being generated and published.
FUXA HMI (fuxa)
Role: Provides a web-based interface for visualizing real-time sensor data and predictions, and potentially sending control commands.
Connections:
Subscribes to MQTT topics (ai_scada/data/# and ai_scada/predictions/#) via mqtt-broker to display data.
Our Work: We focused heavily on securely exposing this interface by setting up an Nginx reverse proxy (nginx-fuxa) with basic authentication, allowing you to share access with coworkers via http://<your-machine-ip>.
Nginx Reverse Proxy (nginx-fuxa)
Role: Proxies HTTP requests to the FUXA HMI, adding a layer of security with basic authentication.
Connections:
Listens on port 80 of your host machine.
Forwards requests to fuxa (internal port 1881) after authenticating users.
Our Work: This was a new addition during our session. We configured Nginx with a custom configuration file, set up authentication credentials, and ensured it runs correctly as seen in the logs.
pgAdmin (pgadmin)
Role: A web UI for managing and querying TimescaleDB.
Connections:
Connects to tsdb for database operations (http://localhost:5050).
Our Work: We provided connection details to access tsdb through pgAdmin.
Overall System Flow
Data Generation: pipeline-simulator generates sensor data and publishes it to mqtt-broker.
Data Storage: data-api-service subscribes to this data, processes it, and stores it in tsdb.
Data Analysis: automl-service retrieves historical data from tsdb, trains models, and publishes predictions back to mqtt-broker.
Visualization and Control: fuxa (FUXA HMI) displays real-time data and predictions from mqtt-broker. Access to FUXA is now secured and proxied through nginx-fuxa for external sharing.
This setup creates a focused, modular system optimized for rapid deployment and testing. Components communicate primarily through MQTT for real-time data and use TimescaleDB for persistence and analysis. Our work emphasized connectivity, data flow, and secure access to the visualization layer, enhancing the prototype's usability and security for time series predictive analytics and maintenance.