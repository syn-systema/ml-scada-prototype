# AutoML Service Configuration Guide

This guide provides detailed instructions on how to modify key settings in the `main.py` file of the `automl-service` for controlling training duration and prediction loop intervals. It also covers how to check logs to monitor the service's behavior.

## Table of Contents
- [Modifying Training Time](#modifying-training-time)
- [Modifying Prediction Loop Interval](#modifying-prediction-loop-interval)
- [Checking Logs](#checking-logs)
- [Environment Variables for Overrides](#environment-variables-for-overrides)

## Modifying Training Time

The training duration for the H2O AutoML process is controlled by the `max_runtime_secs` parameter in the `run_automl_training` function. Adjusting this value limits or extends how long the model training can run, which impacts the quality of the trained model and the time it takes to complete.

### Where to Change
- **File**: `main.py`
- **Function**: `run_automl_training`
- **Line**: Approximately line 205 (search for `max_runtime_secs` if the line number has changed)
- **Parameter**: `max_runtime_secs` within the `H2OAutoML` initialization

### How to Change
1. Open `main.py` in a text editor or IDE.
2. Locate the `run_automl_training` function.
3. Find the `H2OAutoML` initialization block:
   ```python
   aml = H2OAutoML(
       max_runtime_secs=30,  # Reduced to 30 seconds for quick demo on local laptops
       seed=1,
       max_models=30,  # Reduced to 30 for better adherence to time limit
       keep_cross_validation_predictions=True,
       verbosity="info",
       stopping_rounds=3,  # Enable early stopping with more aggressive settings
       stopping_tolerance=0.001  # Lower tolerance for quicker stopping
   )
   ```
4. Modify the value of `max_runtime_secs` to your desired duration in seconds. For example:
   - For a quick demo: `max_runtime_secs=30` (30 seconds)
   - For a moderate training session: `max_runtime_secs=300` (5 minutes)
   - For a full training session: `max_runtime_secs=600` (10 minutes, original setting)
5. Save the file.

### Considerations
- Shorter training times (e.g., 30 seconds) are suitable for quick demonstrations or testing on local laptops but may result in less accurate models.
- Longer training times (e.g., 10 minutes) allow for better model performance but can be time-consuming for local development.
- You can also adjust `max_models` to limit the number of models trained, which can further control training duration (e.g., reducing from 30 to 10 for even faster training).

### After Changing
- **Rebuild and Restart the Service**: After modifying `main.py`, rebuild and restart the `automl-service` container to apply the changes:
  ```bash
  sudo docker compose build automl-service && sudo docker compose up -d automl-service
  ```
- **Check Logs**: Monitor the logs to confirm the training duration setting (see [Checking Logs](#checking-logs) section below).

## Modifying Prediction Loop Interval

The prediction loop interval determines how often the AutoML service generates and publishes predictions to MQTT topics. This is controlled by the `PREDICTION_INTERVAL_SECONDS` variable, which can be set via an environment variable or directly in the code.

### Where to Change
- **File**: `main.py`
- **Location**: Near the top of the file, in the environment variables section
- **Line**: Approximately line 36 (search for `PREDICTION_INTERVAL_SECONDS` if the line number has changed)
- **Variable**: `PREDICTION_INTERVAL_SECONDS`

### How to Change
1. Open `main.py` in a text editor or IDE.
2. Locate the environment variables section near the top of the file.
3. Find the line defining `PREDICTION_INTERVAL_SECONDS`:
   ```python
   PREDICTION_INTERVAL_SECONDS = int(os.getenv("PREDICTION_INTERVAL_SECONDS", 1))  # Changed to 1 second for frequent predictions during local testing
   ```
4. Modify the default value (the second argument of `os.getenv`) to your desired interval in seconds. For example:
   - For frequent predictions (demo/testing): `1` (every second)
   - For standard operation: `30` (every 30 seconds, original setting)
   - For less frequent predictions: `60` (every minute)
5. Save the file.

### Considerations
- Setting the interval to a very short duration (e.g., 1 second) is useful for demonstrations to show rapid updates but may overload the system or MQTT broker if too many messages are published.
- Longer intervals (e.g., 30 or 60 seconds) are more suitable for production environments to reduce system load.

### After Changing
- **Rebuild and Restart the Service**: After modifying `main.py`, rebuild and restart the `automl-service` container to apply the changes:
  ```bash
  sudo docker compose build automl-service && sudo docker compose up -d automl-service
  ```
- **Check Logs**: Monitor the logs to confirm the prediction interval (see [Checking Logs](#checking-logs) section below).

## Checking Logs

Monitoring the logs of the `automl-service` container is essential to verify that your configuration changes have taken effect and to troubleshoot any issues.

### How to Check Logs
1. **Open a Terminal**: Navigate to the project directory where `docker-compose.yml` is located:
   ```bash
   cd /path/to/agentic-scada-master
   ```
2. **View Logs**: Use the following command to view the logs for the `automl-service`:
   ```bash
   sudo docker compose logs automl-service --tail 50 --follow
   ```
   - `--tail 50`: Limits the output to the last 50 lines to avoid overwhelming output.
   - `--follow`: Keeps the log output streaming in real-time to see new log entries as they are generated.
3. **Filter Logs (Optional)**: To focus on specific information, you can filter the logs using `grep`. For example:
   - To check training duration:
     ```bash
     sudo docker compose logs automl-service --since 5m | grep -i 'training'
     ```
   - To check prediction cycle timing:
     ```bash
     sudo docker compose logs automl-service --since 5m | grep -i 'prediction cycle'
     ```
   - To check for errors:
     ```bash
     sudo docker compose logs automl-service --since 5m | grep -i 'error'
     ```

### What to Look for in Logs
- **Training Duration**:
  - Look for log entries mentioning `max_runtime_secs` or messages like "Starting AutoML training..." followed by completion messages to estimate the actual training time.
  - Example log entry: `aml = H2OAutoML(max_runtime_secs=30, ...)` or `AutoML training completed.`
- **Prediction Loop Interval**:
  - Look for log entries at the end of a prediction cycle that mention the sleep time, such as "Prediction Cycle End (Took X.XXs). Sleeping for Y.YYs".
  - Example log entry: `--- Prediction Cycle End (Took 0.33s). Sleeping for 1.00s ---` confirms a 1-second interval.
- **Errors or Issues**:
  - Look for any lines with `ERROR` or `WARNING` to identify problems with training, prediction, or MQTT publishing.

## Environment Variables for Overrides

Instead of hardcoding changes in `main.py`, you can use environment variables to override settings without modifying the code. This approach is recommended for production or when testing different configurations without altering the source file.

### How to Set Environment Variables
1. **In `docker-compose.yml`**:
   - Locate the `automl-service` section.
   - Add or modify environment variables under the `environment` key:
     ```yaml
     automl-service:
       build:
         context: ./services/automl-service
       container_name: automl-service
       restart: unless-stopped
       environment:
         - PREDICTION_INTERVAL_SECONDS=1
         # Other environment variables...
     ```
   - After updating, rebuild and restart the service:
     ```bash
     sudo docker compose build automl-service && sudo docker compose up -d automl-service
     ```
2. **Directly in Terminal (Temporary for Testing)**:
   - Export the variable before running the container:
     ```bash
     export PREDICTION_INTERVAL_SECONDS=1
     sudo docker compose up -d automl-service
     ```
   - Note: This method only applies for the current terminal session and won't persist after a restart.

### Relevant Environment Variables
- **Prediction Loop Interval**: `PREDICTION_INTERVAL_SECONDS`
  - Default in code: `1` (after recent change; originally `30`)
  - Example: Set to `5` for predictions every 5 seconds.
- **Training Time**: There is no direct environment variable for `max_runtime_secs` in the current code. To add this capability, you would need to modify `main.py` to read an environment variable for training duration, such as:
  ```python
  max_runtime_secs = int(os.getenv("MAX_TRAINING_SECONDS", 30))
  aml = H2OAutoML(max_runtime_secs=max_runtime_secs, ...)
  ```
  Then, set `MAX_TRAINING_SECONDS` in `docker-compose.yml` or the terminal.

## Summary
- **Training Time**: Adjust `max_runtime_secs` in `run_automl_training` function of `main.py` (e.g., 30 seconds for demos, 600 for full training).
- **Prediction Loop**: Adjust `PREDICTION_INTERVAL_SECONDS` default value in `main.py` or override via environment variable (e.g., 1 second for frequent updates).
- **Logs**: Use `docker compose logs automl-service` to verify changes, looking for training duration and prediction cycle sleep times.
- **Environment Overrides**: Prefer setting environment variables in `docker-compose.yml` for configuration changes without modifying code.

After making changes, always rebuild and restart the `automl-service` container to apply them, and check the logs to confirm the new settings are in effect. If you encounter issues or need further customization, refer to the H2O AutoML documentation for additional parameters or consult with your team for specific requirements.
