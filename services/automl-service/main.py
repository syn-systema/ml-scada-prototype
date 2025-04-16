print(">>> main.py execution started <<<") # Basic check

import traceback
import os # Import os module
import requests
from datetime import datetime, timedelta

try:
    import h2o
    import psycopg2
    import pandas as pd
    from datetime import datetime
    from h2o.automl import H2OAutoML
    import logging
    import time
    import paho.mqtt.client as mqtt
    import json

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("automl-service")

    # Environment variables
    DB_USER = os.getenv('POSTGRES_USER', 'default_user')
    DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'default_password')
    DB_HOST = os.getenv('TIMESCALEDB_HOST', 'timescaledb') # Service name in Docker Compose
    DB_PORT = os.getenv('TIMESCALEDB_PORT', '5432')
    DB_NAME = os.getenv('POSTGRES_DB', 'scada_db')

    MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")
    MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", "automl-service")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "") # IMPORTANT: Set this in docker-compose env
    MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "automl-service-client")
    MQTT_PREDICTION_TOPIC_PREFIX = "ai_scada/predictions"
    PREDICTION_INTERVAL_SECONDS = int(os.getenv("PREDICTION_INTERVAL_SECONDS", 30)) # How often to predict
    SENSORS_TO_PREDICT = ["pressure-1", "temp-1", "flow-1", "pressure-2", "flow-2", "vibration-1", "pressure-3", "flow-3", "temp-2", "oil-production", "gas-production", "water-cut", "valve-inlet", "valve-gas", "valve-water", "valve-oil", "temp-3"] # Updated to include all 17 sensors
    H2O_MODEL_ID = os.getenv("H2O_MODEL_ID", "") # Optional: Specify a pre-trained model ID or path to load

    mqtt_client = None
    trained_model = None # Will hold the best model after training
    feature_columns = None # Will hold the feature column names

    # MQTT Callbacks
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected successfully to MQTT Broker: {MQTT_BROKER_HOST}")
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")

    def on_publish(client, userdata, mid):
        logger.debug(f"Message Published (MID: {mid})")

    def setup_mqtt_client() -> mqtt.Client | None:
        """Sets up and connects the MQTT client."""
        global mqtt_client
        try:
            logger.info(f"Setting up MQTT client for broker {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
            mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
            mqtt_client.on_connect = on_connect
            mqtt_client.on_publish = on_publish

            if MQTT_USERNAME and MQTT_PASSWORD:
                logger.info(f"Using username '{MQTT_USERNAME}' for MQTT connection.")
                mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            else:
                logger.warning("MQTT username or password not set. Connecting anonymously (if allowed by broker).")

            mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
            mqtt_client.loop_start() # Start background thread for network traffic
            return mqtt_client
        except Exception as e:
            logger.error(f"Error setting up MQTT client: {e}", exc_info=True)
            mqtt_client = None
            return None

    def fetch_training_data():
        """Fetches training data for specified sensors from TimescaleDB."""
        try:
            conn_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            logger.info(f"Connecting to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()
            target_sensors = tuple(SENSORS_TO_PREDICT)
            logger.info(f"Fetching data for sensors: {target_sensors}")
            # Modified query to fetch data for specific sensors
            query = """
                SELECT sensor_id, timestamp, value
                FROM sensor_data
                WHERE sensor_id IN %s
                ORDER BY timestamp DESC
            """
            cursor.execute(query, (target_sensors,))
            data = cursor.fetchall()
            colnames = [desc[0] for desc in cursor.description]
            cursor.close()
            conn.close()
            logger.info(f"Fetched {len(data)} records.")
            df = pd.DataFrame(data, columns=colnames)
            logger.info(f"[Training] Sample training data (first 10 rows):\n{df.head(10).to_string()}")
            logger.info(f"[Training] Training data shape: {df.shape}")
            logger.info(f"[Training] Training data columns: {list(df.columns)}")
            # Log a random sample grouped by sensor (if 'sensor' in columns)
            if 'sensor' in df.columns:
                grouped = df.groupby('sensor')
                for sensor, group in grouped:
                    logger.info(f"[Training] Random sample for sensor '{sensor}':\n{group.sample(min(3, len(group))).to_string(index=False)}")
            return df
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return None

    def process_data(df, fit_encoders=True, existing_df=None):
        """Processes the data: extracts time features and one-hot encodes sensor_id."""
        if df is None or df.empty:
            logger.warning("process_data called with empty or None DataFrame.")
            return None

        logger.info(f"Processing data... Input shape: {df.shape}")
        logger.info(f"Input data:\n{df.to_string()}")
        processed = df.copy()

        # Convert timestamp to datetime objects if they aren't already
        processed['timestamp'] = pd.to_datetime(processed['timestamp'])

        # Extract time-based features
        processed['year'] = processed['timestamp'].dt.year
        processed['month'] = processed['timestamp'].dt.month
        processed['day'] = processed['timestamp'].dt.day
        processed['hour'] = processed['timestamp'].dt.hour
        processed['minute'] = processed['timestamp'].dt.minute
        processed['second'] = processed['timestamp'].dt.second
        processed['dayofweek'] = processed['timestamp'].dt.dayofweek

        # One-hot encode sensor_id
        if 'sensor_id' in processed.columns:
            try:
                # Create dummy variables for sensor_id
                sensor_dummies = pd.get_dummies(processed['sensor_id'], prefix='sensor_id')
                logger.info(f"Created sensor dummies:\n{sensor_dummies.to_string()}")
                
                # Initialize all possible sensor columns with 0
                all_sensor_columns = [f'sensor_id_{sensor}' for sensor in SENSORS_TO_PREDICT]
                for col in all_sensor_columns:
                    if col not in sensor_dummies.columns:
                        sensor_dummies[col] = 0
                
                processed = pd.concat([processed, sensor_dummies], axis=1)
                
                # Drop the original sensor_id column
                processed = processed.drop('sensor_id', axis=1)
                
                logger.debug(f"One-hot encoded columns: {sensor_dummies.columns.tolist()}")
            except Exception as e:
                logger.error(f"Error during one-hot encoding: {e}", exc_info=True)
                return None

        # Drop original timestamp column
        if 'timestamp' in processed.columns:
            processed = processed.drop('timestamp', axis=1)

        # Keep historical values and rates of change if they exist, otherwise initialize to 0
        historical_features = ['prev_value_1', 'prev_value_2', 'prev_value_3', 
                             'rate_of_change_1', 'rate_of_change_2']
        for feature in historical_features:
            if feature not in processed.columns:
                logger.warning(f"Missing historical feature: {feature}, initializing to 0")
                processed[feature] = 0

        # Base required features (excluding sensor IDs)
        required_features = ['year', 'month', 'day', 'hour', 'minute', 'second', 'dayofweek',
                           'prev_value_1', 'prev_value_2', 'prev_value_3',
                           'rate_of_change_1', 'rate_of_change_2']
        
        # Include 'value' only if it's in the DataFrame (for training data)
        if 'value' in processed.columns:
            required_features.insert(0, 'value')
        
        # Add sensor ID columns to required features
        required_features.extend([f'sensor_id_{sensor}' for sensor in SENSORS_TO_PREDICT])
        
        missing_features = [f for f in required_features if f not in processed.columns]
        if missing_features:
            logger.error(f"Missing required features: {missing_features}")
            return None

        # Reorder columns to match training data
        processed = processed[required_features]

        logger.info(f"Processed data shape: {processed.shape}")
        logger.info(f"Final data:\n{processed.to_string()}")
        return processed

    def run_automl_training(h2o_frame):
        """Run AutoML training on the provided H2O frame."""
        try:
            logger.info("Starting AutoML training...")
            logger.info(f"Training data shape: {h2o_frame.shape}")
            logger.info(f"Training data columns: {h2o_frame.columns}")
            logger.info(f"Training data types: {h2o_frame.types}")
            logger.info(f"Training data summary:\n{h2o_frame.describe()}")
            logger.info(f"Training dataset size: {h2o_frame.nrows} rows, {h2o_frame.ncols} columns")
            
            aml = H2OAutoML(
                max_runtime_secs=120,  # 10 minutes
                seed=1,
                max_models=10,  # Reduced to 30 to better adhere to the 10-minute limit
                keep_cross_validation_predictions=True,
                verbosity="info",
                stopping_rounds=3,  # Enable early stopping with more aggressive settings
                stopping_tolerance=0.001  # Lower tolerance for quicker stopping
            )
            
            # Identify predictors (all columns except 'value')
            predictors = [col for col in h2o_frame.columns if col != 'value']
            response = 'value'
            
            logger.info(f"Training with predictors: {predictors}")
            logger.info(f"Response column: {response}")
            
            # Train the model
            aml.train(x=predictors, y=response, training_frame=h2o_frame)
            
            # Log training results
            logger.info("AutoML training completed.")
            logger.info(f"Best model: {aml.leader.model_id}")
            logger.info(f"Best model performance: {aml.leader.model_performance()}")
            
            return aml
            
        except Exception as e:
            logger.error(f"Error during AutoML training: {e}", exc_info=True)
            return None

    def fetch_latest_data_for_prediction(sensors: list) -> pd.DataFrame | None:
        """Fetches the latest real data from TimescaleDB for each sensor and prepares for 30s future prediction."""
        try:
            conn_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()

            # Get recent data points for trend analysis
            query = """
                WITH RankedData AS (
                    SELECT 
                        sensor_id,
                        timestamp,
                        value,
                        LAG(value, 1) OVER (PARTITION BY sensor_id ORDER BY timestamp) as prev_value_1,
                        LAG(value, 2) OVER (PARTITION BY sensor_id ORDER BY timestamp) as prev_value_2,
                        LAG(value, 3) OVER (PARTITION BY sensor_id ORDER BY timestamp) as prev_value_3,
                        EXTRACT(EPOCH FROM (timestamp - LAG(timestamp, 1) OVER (PARTITION BY sensor_id ORDER BY timestamp))) as time_diff_1,
                        EXTRACT(EPOCH FROM (timestamp - LAG(timestamp, 2) OVER (PARTITION BY sensor_id ORDER BY timestamp))) as time_diff_2,
                        EXTRACT(EPOCH FROM (timestamp - LAG(timestamp, 3) OVER (PARTITION BY sensor_id ORDER BY timestamp))) as time_diff_3
                    FROM sensor_data
                    WHERE 
                        sensor_id = ANY(%s)
                        AND timestamp >= NOW() - INTERVAL '5 minutes'
                )
                SELECT 
                    sensor_id,
                    timestamp,
                    value,
                    prev_value_1,
                    prev_value_2,
                    prev_value_3,
                    time_diff_1,
                    time_diff_2,
                    time_diff_3,
                    -- Calculate rate of change
                    CASE 
                        WHEN time_diff_1 > 0 THEN (value - prev_value_1) / time_diff_1 
                        ELSE 0 
                    END as rate_of_change_1,
                    CASE 
                        WHEN time_diff_2 > 0 THEN (value - prev_value_2) / time_diff_2 
                        ELSE 0 
                    END as rate_of_change_2,
                    ROW_NUMBER() OVER (PARTITION BY sensor_id ORDER BY timestamp DESC) as rn
                FROM RankedData
                WHERE prev_value_3 IS NOT NULL
                ORDER BY sensor_id, timestamp DESC
            """
            
            cursor.execute(query, (sensors,))
            latest_data = cursor.fetchall()
            cursor.close()
            conn.close()

            if not latest_data:
                logger.error("No recent data found for sensors!")
                return None

            # Create DataFrame with the latest values and calculated features
            columns = ['sensor_id', 'timestamp', 'value', 'prev_value_1', 'prev_value_2', 'prev_value_3', 
                      'time_diff_1', 'time_diff_2', 'time_diff_3', 'rate_of_change_1', 'rate_of_change_2', 'rn']
            df = pd.DataFrame(latest_data, columns=columns)
            
            # Filter to keep only the latest 3 data points per sensor
            df = df[df['rn'] <= 3].drop('rn', axis=1)
            
            # Create prediction data with the actual last timestamp and features
            prediction_data = []
            for sensor_id in sensors:
                sensor_df = df[df['sensor_id'] == sensor_id]
                if not sensor_df.empty:
                    # Use the most recent row for this sensor
                    row = sensor_df.iloc[0]
                    prediction_row = {
                        'sensor_id': row['sensor_id'],
                        'timestamp': row['timestamp'],  # Use actual last timestamp for time features
                        'prev_value_1': row['value'],  # Current value becomes previous value
                        'prev_value_2': row['prev_value_1'],
                        'prev_value_3': row['prev_value_2'],
                        'rate_of_change_1': row['rate_of_change_1'],
                        'rate_of_change_2': row['rate_of_change_2'],
                    }
                    prediction_data.append(prediction_row)
                else:
                    logger.warning(f"No recent data found for sensor {sensor_id}")

            if not prediction_data:
                logger.error("No prediction data created for any sensor!")
                return None

            prediction_df = pd.DataFrame(prediction_data)
            logger.info(f"Created prediction data:\n{prediction_df.to_string()}")
            
            # Return the unprocessed prediction data
            return prediction_df
        
        except Exception as e:
            logger.error(f"Error fetching latest data for prediction: {e}", exc_info=True)
            return None

    def make_predictions(model, data_hf):
        """Uses the trained H2O model to make predictions."""
        if model is None or data_hf is None:
            logger.warning("Cannot make predictions: Model or prediction data is missing.")
            return None
        try:
            logger.info("Making predictions with the trained model...")
            predictions = model.predict(data_hf)
            logger.info("Predictions generated.")
            # Log prediction details
            with h2o.display.capture_output() as (original_output, captured_output):
                predictions.describe()
            logger.info(f"Prediction H2OFrame describe:\n{captured_output.getvalue()}")
            return predictions
        except Exception as e:
            logger.error(f"Error during prediction: {e}", exc_info=True)
            return None

    def prediction_loop():
        """Main loop for fetching data, predicting, and publishing."""
        global trained_model, feature_columns, mqtt_client

        if not trained_model or not feature_columns:
            logger.error("Cannot start prediction loop: Model not trained or features not set.")
            return

        if not mqtt_client or not mqtt_client.is_connected():
            logger.error("Cannot start prediction loop: MQTT client not connected.")
            # Optional: Attempt to reconnect here
            return

        logger.info(f"Starting prediction loop. Interval: {PREDICTION_INTERVAL_SECONDS} seconds.")
        while True:
            try:
                start_time = time.time()
                logger.info("--- Prediction Cycle Start ---")

                # 1. Fetch latest data needed for the model
                # This needs modification based on the actual features the model expects.
                prediction_data = fetch_latest_data_for_prediction(SENSORS_TO_PREDICT)

                if prediction_data is None:
                    logger.error("Failed to get prediction data")
                    time.sleep(PREDICTION_INTERVAL_SECONDS)
                    continue

                # Keep a copy of original data with sensor_id for later use
                original_prediction_data = prediction_data.copy()

                # Process the data for prediction
                processed_prediction_data = process_data(prediction_data)
                if processed_prediction_data is None:
                    logger.error("Failed to process prediction data")
                    time.sleep(PREDICTION_INTERVAL_SECONDS)
                    continue

                # Log the processed prediction data
                logger.info("Processed prediction data:")
                logger.info(f"Shape: {processed_prediction_data.shape}")
                logger.info(f"Columns: {processed_prediction_data.columns.tolist()}")
                logger.info(f"Data:\n{processed_prediction_data.to_string()}")

                # Convert to H2OFrame
                h2o_frame = h2o.H2OFrame(processed_prediction_data)
                logger.info("H2O Frame for prediction:")
                logger.info(f"Shape: {h2o_frame.shape}")
                logger.info(f"Columns: {h2o_frame.columns}")
                logger.info(f"Types: {h2o_frame.types}")
                logger.info(f"Summary:\n{h2o_frame.describe()}")

                # Generate predictions
                predictions = make_predictions(trained_model, h2o_frame)
                logger.info("Predictions generated.")
                logger.info(f"Prediction H2OFrame describe:\n{predictions.describe()}")

                if predictions is not None:
                    # 4. Format and Publish Predictions via MQTT
                    try:
                        predictions_df = predictions.as_data_frame()
                        # Combine prediction with original sensor ID if needed
                        # Assuming predictions_df has a 'predict' column
                        # And original_prediction_data has the 'sensor_id' column
                        results_df = pd.concat([original_prediction_data[['sensor_id']].reset_index(drop=True), 
                                                predictions_df[['predict']].reset_index(drop=True)], axis=1)
                        
                        logger.info(f"Generated predictions: {results_df.to_dict('records')}")

                        for index, row in results_df.iterrows():
                            sensor_id = row['sensor_id']
                            predicted_value = row['predict']
                            topic = f"{MQTT_PREDICTION_TOPIC_PREFIX}/{sensor_id}"
                            payload = json.dumps({
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "sensor_id": sensor_id,
                                "value": predicted_value,
                                "type": "prediction"
                            })
                            logger.info(f"Publishing to {topic}: {payload}")
                            result = mqtt_client.publish(topic, payload=payload, qos=0)
                            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                                 logger.error(f"Failed to publish prediction for {sensor_id} to {topic}. RC: {result.rc}")
                            else:
                                 logger.debug(f"Successfully queued prediction for {sensor_id} (MID: {result.mid})")

                    except Exception as e:
                        logger.error(f"Error formatting or publishing predictions: {e}", exc_info=True)
                else:
                    logger.warning("Skipping prediction cycle: No predictions generated.")

                # Wait for the next interval
                elapsed_time = time.time() - start_time
                sleep_time = max(0, PREDICTION_INTERVAL_SECONDS - elapsed_time)
                logger.info(f"--- Prediction Cycle End (Took {elapsed_time:.2f}s). Sleeping for {sleep_time:.2f}s ---")
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Unexpected error in prediction loop: {e}", exc_info=True)
                # Avoid rapid looping on persistent errors
                time.sleep(PREDICTION_INTERVAL_SECONDS)


    def main():
        global trained_model
        trained_model = None  # Initialize to prevent UnboundLocalError
        logger.info("Starting AutoML Service...")

        # Setup MQTT Client first
        if not setup_mqtt_client():
            logger.critical("Failed to setup MQTT Client. Exiting.")
            return

        # Initialize H2O cluster
        try:
            logger.info("Initializing H2O cluster...")
            h2o.init()
            logger.info("H2O cluster initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize H2O cluster: {e}")
            return

        # Check if a pre-trained model ID or path is provided
        if H2O_MODEL_ID:
            try:
                logger.info(f"Loading pre-trained model: {H2O_MODEL_ID}")
                trained_model = h2o.get_model(H2O_MODEL_ID) if not H2O_MODEL_ID.startswith('/') else h2o.load_model(H2O_MODEL_ID)
                logger.info(f"Successfully loaded pre-trained model: {H2O_MODEL_ID}")
                # Fetch feature columns from model or assume default
                global feature_columns
                feature_columns = trained_model.varimp(use_pandas=True)['variable'].tolist() if trained_model.varimp() else []
                logger.info(f"Feature columns from model: {feature_columns}")
            except Exception as e:
                logger.error(f"Failed to load pre-trained model {H2O_MODEL_ID}: {e}")
                trained_model = None

        # Train model only if no pre-trained model was loaded
        if not trained_model:
            logger.info("Fetching training data...")
            training_df = fetch_training_data()

            if training_df is not None and not training_df.empty:
                logger.info("Processing training data...")
                processed_df = process_data(training_df)
                if processed_df is not None:
                    logger.info("Converting processed data to H2OFrame with specified types...")
                    try:
                        # Create column types dictionary
                        column_types = {}
                        for col in processed_df.columns:
                            if pd.api.types.is_datetime64_any_dtype(processed_df[col]):
                                column_types[col] = 'time'
                            elif pd.api.types.is_float_dtype(processed_df[col]):
                                column_types[col] = 'real'
                            elif pd.api.types.is_integer_dtype(processed_df[col]):
                                column_types[col] = 'int'
                            elif pd.api.types.is_categorical_dtype(processed_df[col]):
                                column_types[col] = 'categorical'
                            elif pd.api.types.is_object_dtype(processed_df[col]):
                                if col.startswith('sensor_id_'):
                                    column_types[col] = 'int'
                                else:
                                    column_types[col] = 'string'
                            else:
                                column_types[col] = 'string'
                        
                        if 'value' in column_types:
                            column_types['value'] = 'real'
                        if 'prev_value' in column_types:
                            column_types['prev_value'] = 'real'
                        if 'prev_value_2' in column_types:
                            column_types['prev_value_2'] = 'real'
                        
                        logger.info(f"Dynamic column types created: {column_types}")
                        
                        # Create H2OFrame with the dynamic column types
                        h2o_training_frame = h2o.H2OFrame(processed_df, column_types=column_types)
                        logger.info("Training data successfully converted to H2OFrame.")
                        
                        # Set feature columns for prediction loop
                        feature_columns = processed_df.columns.tolist()
                        logger.info(f"Feature columns set for prediction: {feature_columns}")
                        
                        # Run AutoML training once
                        trained_model = run_automl_training(h2o_training_frame)
                        
                    except Exception as e:
                        logger.error(f"Error during H2OFrame conversion or processing: {e}")
                        return  # Exit if training fails
            else:
                logger.error("No training data fetched or data is empty. Cannot proceed.")
                return

        # Start the prediction loop only if the model was trained successfully
        if trained_model:
            prediction_loop()
        else:
            logger.error("Model training failed. Service cannot proceed.")
            return

        try:
            pass
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main execution block: {e}", exc_info=True)
        finally:
            if mqtt_client:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
                logger.info("MQTT client disconnected.")

            if h2o.connection():
                h2o.cluster().shutdown()
                logger.info("H2O cluster shut down.")

    if __name__ == "__main__":
        main()

except Exception as e:
    print("!!! EXCEPTION CAUGHT IN main.py !!!")
    traceback.print_exc()
    # Keep the container running briefly to allow log inspection
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    time.sleep(60)