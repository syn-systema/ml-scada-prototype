# AutoML Service

This service uses H2O.ai's AutoML to train machine learning models on time series data from sensors and generate predictions. It integrates with the AI SCADA system to provide predictive analytics for maintenance and operational efficiency.

## Key Features
- **Automated Model Training**: Uses H2O AutoML to train models on historical sensor data.
- **Real-Time Predictions**: Generates predictions for sensor values and publishes them to MQTT topics.
- **H2O Flow UI**: Accessible at `http://localhost:54321` for interactive model training and evaluation.
- **Custom Model Deployment**: Allows users to specify a pre-trained model for predictions using the `H2O_MODEL_ID` environment variable.

## Configuration

Environment variables can be set in the `docker-compose.yml` file or in a `.env` file:

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: Credentials and database name for TimescaleDB.
- `TIMESCALEDB_HOST`, `TIMESCALEDB_PORT`: Host and port for TimescaleDB connection.
- `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_CLIENT_ID`: MQTT broker connection details.
- `PREDICTION_INTERVAL_SECONDS`: How often predictions are generated (default: 10 seconds).
- `H2O_MODEL_ID`: Optional. Specify the ID or path of a pre-trained H2O model to use for predictions. If not set, a new model will be trained on startup.

## Using H2O Flow UI

1. Access the UI at `http://localhost:54321`.
2. Explore data, train models using AutoML, and evaluate performance.
3. Save a model you want to deploy. Note the model ID (visible in the UI) or export the model to a file.
4. Set the `H2O_MODEL_ID` environment variable in `docker-compose.yml` or your `.env` file to the model ID or file path (if exported to `/app/h2o_models` in the container).
5. Restart the `automl-service` container to use the specified model for automated predictions.

## Volumes
- `./data/h2o_models:/app/h2o_models`: Persists trained models and allows users to export/import models for deployment.

## Development
To modify the service, edit `main.py` or other files in `./services/automl-service`. Rebuild the image with `docker compose build automl-service` and restart with `docker compose up -d automl-service`.
