#!/bin/bash

# Set the path to the H2O JAR file (adjust if necessary)
# Assuming it's installed via pip and located in site-packages
# Find the h2o.jar file within the Python environment
H2O_JAR_PATH=$(python -c "import h2o, os; print(os.path.join(os.path.dirname(h2o.__file__), 'backend', 'bin', 'h2o.jar'))")

if [ ! -f "$H2O_JAR_PATH" ]; then
    echo "Error: H2O JAR file not found!"
    exit 1
fi

# Start H2O server in the background
echo "Starting H2O server in background..."
java -jar "${H2O_JAR_PATH}" -port 54321 &

# Wait until H2O Cloud status endpoint returns 200 OK
echo "Waiting for H2O server to initialize..."
while [[ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:54321/3/Cloud)" != "200" ]]; do 
    echo "H2O server not ready yet (checking /3/Cloud), waiting..."; 
    sleep 2;
done
echo "H2O server is up!"

# Now execute the main Python application
echo "Starting Python application..."
python main.py

# --- DEBUG --- 
# Test basic python execution
# echo "Attempting basic Python execution..."
# python -c "print('>>> Python executed successfully from entrypoint <<<' )"
# echo "Python execution attempt finished."