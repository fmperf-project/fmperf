#!/bin/bash

# Configuration variables - edit these as needed
DEFAULT_LOG_DIR_PREFIX="$(pwd)/logs"
DEFAULT_GRACE_PERIOD_MINUTES=2
EXCLUDE_PATTERNS=(                   # Patterns to exclude from logs
  "GET /health HTTP/1.1"
  "GET /metrics HTTP/1.1"
)

# Detect platform for date command
PLATFORM=$(uname)
if [ "$PLATFORM" = "Darwin" ]; then
  # macOS
  DATE_READABLE_CMD="date -r"
elif [ "$PLATFORM" = "Linux" ]; then
  # Linux
  DATE_READABLE_CMD="date -d @"
else
  echo "Unsupported platform: $PLATFORM"
  exit 1
fi

# Default label selector for vllm pods
DEFAULT_LABEL_KEY="app"
DEFAULT_LABEL_VALUE="vllm-llama-3-70b"

# Parse command line arguments
LABEL_KEY=$DEFAULT_LABEL_KEY
LABEL_VALUE=$DEFAULT_LABEL_VALUE
LOG_DIR_PREFIX=$DEFAULT_LOG_DIR_PREFIX
GRACE_PERIOD_MINUTES=$DEFAULT_GRACE_PERIOD_MINUTES
PODS=()
RUN_IN_BACKGROUND=false
JOB_NAME=""

# Create log directory with timestamp first
LOG_DIR="${LOG_DIR_PREFIX}/pod_logs_$(date +%Y%m%d_%H%M%S)"
PID_FILE="${LOG_DIR}/.pid"
mkdir -p "$LOG_DIR"

while [[ $# -gt 0 ]]; do
  case $1 in
    --label-key=*)
      LABEL_KEY="${1#*=}"
      shift
      ;;
    --label-value=*)
      LABEL_VALUE="${1#*=}"
      shift
      ;;
    --log-dir=*)
      LOG_DIR_PREFIX="${1#*=}"
      shift
      ;;
    --job=*)
      JOB_NAME="${1#*=}"
      shift
      ;;
    --grace-period=*)
      GRACE_PERIOD_MINUTES="${1#*=}"
      shift
      ;;
    --background)
      RUN_IN_BACKGROUND=true
      shift
      ;;
    --background=*)
      if [ "${1#*=}" = "true" ]; then
        RUN_IN_BACKGROUND=true
      fi
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--label-key=KEY] [--label-value=VALUE] [--job=JOB_NAME] [--grace-period=MINUTES] [--log-dir=DIR] [--background]"
      exit 1
      ;;
  esac
done

# Get pod names based on label selector if no pods were specified
if [ ${#PODS[@]} -eq 0 ]; then
  echo "Using label selector: $LABEL_KEY=$LABEL_VALUE"
  # Get vllm pods
  vllm_pods=($(oc get pods -l "$LABEL_KEY=$LABEL_VALUE" -o jsonpath='{.items[*].metadata.name}'))
  if [ ${#vllm_pods[@]} -eq 0 ]; then
    echo "No pods found with label $LABEL_KEY=$LABEL_VALUE"
    exit 1
  fi
  PODS+=("${vllm_pods[@]}")
  
  # Always add endpoint-picker pod
  echo "Adding endpoint-picker pod"
  endpoint_pods=($(oc get pods -l app=endpoint-picker -o jsonpath='{.items[*].metadata.name}'))
  if [ ${#endpoint_pods[@]} -gt 0 ]; then
    PODS+=("${endpoint_pods[@]}")
  else
    echo "Warning: No endpoint-picker pods found"
  fi
fi

# Function to cleanup on exit
cleanup() {
  if [ -f "$PID_FILE" ]; then
    rm -f "$PID_FILE"
  fi
  echo "Log collection stopped at $(date)"
  exit 0
}

# Register cleanup function
trap cleanup EXIT

# Function to get logs for a pod with exclusions
get_filtered_logs() {
  local pod=$1
  local log_file="$LOG_DIR/${pod}.log"
  
  # Start building the command
  cmd="oc logs $pod --since=30s"
  
  # Add grep exclusions if any
  for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    cmd="$cmd | grep -v \"$pattern\""
  done
  
  # Add output redirection
  cmd="$cmd >> \"$log_file\""
  
  # Execute the command
  eval "$cmd"
  
  # If log is not empty, print a message
  if [ -s "$log_file" ]; then
    echo "[$(date +%H:%M:%S)] New logs captured for $pod" >> "$LOG_DIR/status.log"
  fi
}

# Function to check if job is complete
check_job_complete() {
  if [ -z "$JOB_NAME" ]; then
    return 1
  fi
  
  local job_status=$(oc get job "$JOB_NAME" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')
  if [ "$job_status" = "True" ]; then
    return 0
  fi
  return 1
}

# Main logging function
main() {
  # Create log directory
  mkdir -p "$LOG_DIR"
  echo "Logs will be saved to $LOG_DIR"
  if [ -n "$JOB_NAME" ]; then
    echo "Monitoring job: $JOB_NAME"
    echo "Will continue logging for $GRACE_PERIOD_MINUTES minutes after job completion"
  fi
  echo "Monitoring pods: ${PODS[*]}"

  echo "=== Starting log collection at $(date) ===" > "$LOG_DIR/status.log"
  if [ -n "$JOB_NAME" ]; then
    echo "Monitoring job: $JOB_NAME" >> "$LOG_DIR/status.log"
    echo "Will continue logging for $GRACE_PERIOD_MINUTES minutes after job completion" >> "$LOG_DIR/status.log"
  fi
  echo "Excluding patterns: ${EXCLUDE_PATTERNS[*]}" >> "$LOG_DIR/status.log"

  local job_complete=false
  local grace_period_end=0

  # Main loop
  while true; do
    # Check if job is complete
    if ! $job_complete && check_job_complete; then
      job_complete=true
      grace_period_end=$(($(date +%s) + GRACE_PERIOD_MINUTES * 60))
      echo "Job $JOB_NAME completed at $(date)" >> "$LOG_DIR/status.log"
      echo "Continuing logging for $GRACE_PERIOD_MINUTES minutes" >> "$LOG_DIR/status.log"
    fi

    # Collect logs
    for pod in "${PODS[@]}"; do
      get_filtered_logs "$pod"
    done

    # Check if we should stop
    if $job_complete && [ $(date +%s) -ge $grace_period_end ]; then
      echo "Grace period ended at $(date)" >> "$LOG_DIR/status.log"
      break
    fi

    sleep 30
  done

  echo "=== Log collection completed at $(date) ===" >> "$LOG_DIR/status.log"
}

# Run in background if requested
if [ "$RUN_IN_BACKGROUND" = true ]; then
  # Start the script in background
  main > /dev/null 2>&1 &
  PID=$!
  
  # Save PID
  echo $PID > "$PID_FILE"
  echo "Log collection started in background. PID: $PID"
  echo "Logs directory: $LOG_DIR"
  echo "To stop logging, run: kill $PID"
else
  # Run in foreground
  main
fi