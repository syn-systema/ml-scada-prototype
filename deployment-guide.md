# AI SCADA System Deployment Guide

**Goal:** To reliably start all services using `docker compose up -d` with minimal manual intervention after the initial setup.

**Assumptions:**

*   You are starting in a clean directory or have removed previous Docker volumes/containers related to this project (`docker compose down -v` is useful for a clean slate).
*   The source code reflects the final working state (e.g., correct MQTT topics in `data-api-service`, etc.).

**Steps:**

1.  **Prerequisites:**
    *   Ensure you have `git`, `Docker`, and `Docker Compose` installed on your system.

2.  **Get the Code:**
    *   Clone the project repository:
        ```bash
        git clone <your-repository-url> agentic-scada-master
        cd agentic-scada-master
        ```

3.  **Configure MQTT Authentication:**
    *   **Crucial:** This must be done *before* the MQTT broker starts enforcing authentication, otherwise dependent services will fail to connect initially.
    *   Make the script executable:
        ```bash
        chmod +x ./scripts/create-mqtt-users.sh
        ```
    *   Run the script to generate the password file (`./config/mosquitto/passwd`):
        ```bash
        ./scripts/create-mqtt-users.sh
        ```
    *   **Verify ACL:** Double-check the `./config/mosquitto/acl` file. Ensure it grants the necessary permissions, especially [read](cci:1://file:///home/farseer/Projects/agentic-scada-master/services/gnn-prediction-service/main.py:90:0-92:59) access for `hmi-client` and `automl-service` to the relevant topics (like `ai_scada/data/#` and `ai_scada/predictions/#` respectively). The configuration from our session should be correct, but verifying is good practice.

4.  **Build Docker Images:**
    *   Build the images for services that have a `build:` instruction in `docker-compose.yml` (e.g., `data-api-service`, `pipeline-simulator`, `automl-service`).
        ```bash
        sudo docker compose build
        ```

5.  **Initial System Startup:**
    *   Start all services defined in `docker-compose.yml` in detached mode:
        ```bash
        sudo docker compose up -d
        ```
    *   **Wait:** Allow 1-2 minutes for services, especially `tsdb`, to initialize.

6.  **Verification (Check Container Status):**
    *   Verify that all containers are running and healthy:
        ```bash
        sudo docker compose ps
        ```
    *   Look for `Up` status and [(healthy)](cci:1://file:///home/farseer/Projects/agentic-scada-master/services/gnn-prediction-service/main.py:90:0-92:59) if applicable.

7.  **Verification (Check Logs - Potential First Hurdle):**
    *   **Check `tsdb`:** Ensure readiness (`database system is ready to accept connections`).
        ```bash
        sudo docker compose logs --tail=50 tsdb
        ```
    *   **Check `data-api-service`:** Verify connections to `tsdb` and `mqtt-broker` and data reception/storage.
        ```bash
        sudo docker compose logs --tail=100 data-api-service
        ```
        *   **If `Connection refused` for `tsdb`:** Restart `data-api-service`:
            ```bash
            sudo docker compose restart data-api-service
            ```
            Then check its logs again.
    *   **Check `automl-service`:** Verify MQTT connection and successful data fetch (look for "Fetched X records" > 0, followed by training logs).
        ```bash
        sudo docker compose logs --tail=200 automl-service
        ```
        *   **If "Fetched 0 records" or similar:** `data-api-service` might not have been ready. Restart `automl-service`:
            ```bash
            sudo docker compose restart automl-service
            ```
            Then check its logs again.

8.  **Configure Fuxa HMI:**
    *   Access Fuxa UI: `http://localhost:1881`
    *   Go to `Settings` -> `Connections` -> `Device`.
    *   Add/Edit MQTT connection:
        *   **Name:** `AICSCADA MQTT` (or similar)
        *   **Address:** `mqtt://mqtt-broker:1883`
        *   **Security Mode:** Username/Password
        *   **Client ID:** `fuxa-hmi-client-manual` (unique ID)
        *   **Username:** `hmi-client`
        *   **Password:** `hmi-client-password`
    *   Save and verify connection status (green).
    *   Configure Tags in Fuxa to subscribe to `ai_scada/data/{sensor_id}` and `ai_scada/predictions/{sensor_id}` topics.

9.  **Access Other UIs (Optional):**
    *   **pgAdmin (Database):** `http://localhost:5050`
        *   Login using credentials from `docker-compose.yml`.
        *   Manually add the `tsdb` server:
            *   Host: `tsdb`
            *   Port: `5432`
            *   DB: `scada_timeseries`
            *   User: `scada`
            *   Password: `scadapassword`
    *   **H2O Flow UI (AutoML):** `http://localhost:54321`

This Markdown guide outlines the refined deployment process for the AI SCADA system.