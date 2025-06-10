#!/bin/bash

# Function to launch benchmark with environment variables
launch_benchmark() {
    local env_file=$1
    
    # Source the environment file
    if [ -f "$env_file" ]; then
        echo "📋 Sourcing environment from $env_file"
        set -a  # automatically export all variables
        source "$env_file"
        set +a
    else
        echo "❌ Error: Environment file $env_file not found"
        exit 1
    fi
    
    # Switch to the namespace defined in the env file
    echo "🔄 Switching to namespace: $FMPERF_OPENSHIFT_NAMESPACE"
    oc project "$FMPERF_OPENSHIFT_NAMESPACE" || exit 1
    
    # Launch the benchmark in the background
    echo "🚀 Launching benchmark for $FMPERF_OPENSHIFT_NAMESPACE"
    python3 examples/example_openshift.py &
    
    # Store the process ID
    echo $! > "${FMPERF_OPENSHIFT_NAMESPACE}_benchmark.pid"
    echo "✅ Started benchmark for $FMPERF_OPENSHIFT_NAMESPACE with PID: $(cat ${FMPERF_OPENSHIFT_NAMESPACE}_benchmark.pid)"
}

# Main script
echo "🎯 Starting comparative benchmarks..."

# Launch baseline benchmark
echo "📊 Launching baseline benchmark..."
launch_benchmark "baseline.env"

# Small delay to ensure proper namespace switching
sleep 2

# Launch llm-d benchmark
echo "📊 Launching llm-d benchmark..."
launch_benchmark "llm-d.env"

echo "📈 Both benchmarks have been launched. Monitor their progress using:"
echo "👀 ps -p \$(cat baseline_benchmark.pid)"
echo "👀 ps -p \$(cat llm-d_benchmark.pid)"

# Wait for both processes to complete
wait

# Clean up PID files
rm -f "baseline_benchmark.pid"
rm -f "llm-d_benchmark.pid"

echo "🎉 Both benchmarks have completed." 