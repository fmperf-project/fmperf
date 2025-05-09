#!/bin/bash

# Configuration variables - edit these as needed
DEFAULT_LOG_DIR_PREFIX="$(pwd)/logs"
DEFAULT_GRACE_PERIOD_MINUTES=2
EXCLUDE_PATTERNS=(                   # Patterns to exclude from logs
  "GET /health HTTP/1.1"
  "GET /metrics HTTP/1.1"
)

# Detect platform for date command and array support
PLATFORM=$(uname)
if [ "$PLATFORM" = "Darwin" ]; then
  # macOS - use file-based approach
  DATE_READABLE_CMD="date -r"
  LAST_CAPTURE_DIR=".last_capture"
  USE_FILE_BASED_CAPTURE=true
elif [ "$PLATFORM" = "Linux" ]; then
  # Linux - use associative array
  DATE_READABLE_CMD="date -d @"
  USE_FILE_BASED_CAPTURE=false
  # Initialize last capture times associative array
  declare -A last_capture_times
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

# Create log directory with job name
if [ -n "$JOB_NAME" ]; then
  LOG_DIR="${LOG_DIR_PREFIX}/${JOB_NAME}"
else
  LOG_DIR="${LOG_DIR_PREFIX}/pod_logs_$(date +%Y%m%d_%H%M%S)"
fi
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

  # Add the job's pod and wait for it to start
  if [ -n "$JOB_NAME" ]; then
    echo "Waiting for job pod to start (timeout: 60s)..."
    start_time=$(date +%s)
    timeout=60
    job_pod=""
    
    while [ $(($(date +%s) - start_time)) -lt $timeout ]; do
      job_pods=($(oc get pods -l job-name=$JOB_NAME -o jsonpath='{.items[*].metadata.name}'))
      if [ ${#job_pods[@]} -gt 0 ]; then
        job_pod="${job_pods[0]}"
        pod_status=$(oc get pod $job_pod -o jsonpath='{.status.phase}')
        if [ "$pod_status" = "Running" ]; then
          echo "Job pod $job_pod is running"
          PODS+=("$job_pod")
          break
        fi
      fi
      sleep 5
    done
    
    if [ -z "$job_pod" ]; then
      echo "Timeout waiting for job pod to start after 60 seconds"
      exit 1
    fi
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
  
  # Get current timestamp in RFC3339 format
  local current_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  
  # Start building the command
  if [ "$USE_FILE_BASED_CAPTURE" = true ]; then
    # macOS file-based approach
    local last_capture_file="$LOG_DIR/$LAST_CAPTURE_DIR/${pod}.last"
    if [ ! -f "$last_capture_file" ]; then
      # First time capturing logs for this pod, use 30s ago
      cmd="oc logs $pod --since=30s"
    else
      # Use the last capture time
      local last_time=$(cat "$last_capture_file")
      cmd="oc logs $pod --since-time=$last_time"
    fi
  else
    # Linux associative array approach
    if [ -z "${last_capture_times[$pod]}" ]; then
      # First time capturing logs for this pod, use 30s ago
      cmd="oc logs $pod --since=30s"
    else
      # Use the last capture time
      cmd="oc logs $pod --since-time=${last_capture_times[$pod]}"
    fi
  fi
  
  # Add grep exclusions if any
  for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    cmd="$cmd | grep -v \"$pattern\""
  done
  
  # Add output redirection
  cmd="$cmd >> \"$log_file\""
  
  # Execute the command
  eval "$cmd"
  
  # If log is not empty, update the last capture time
  if [ -s "$log_file" ]; then
    if [ "$USE_FILE_BASED_CAPTURE" = true ]; then
      # macOS file-based approach
      echo "$current_time" > "$last_capture_file"
    else
      # Linux associative array approach
      last_capture_times[$pod]=$current_time
    fi
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

# Function to check if job has errors
check_job_error() {
  if [ -z "$JOB_NAME" ]; then
    return 1
  fi
  
  local job_status=$(oc get job "$JOB_NAME" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')
  if [ "$job_status" = "True" ]; then
    return 0
  fi
  return 1
}

# Function to check if job exists
check_job_exists() {
  if [ -z "$JOB_NAME" ]; then
    return 0
  fi
  
  if oc get job "$JOB_NAME" &>/dev/null; then
    return 0
  fi
  return 1
}

# Main logging function
main() {
  # Create log directory and last capture directory if needed
  mkdir -p "$LOG_DIR"
  if [ "$USE_FILE_BASED_CAPTURE" = true ]; then
    mkdir -p "$LOG_DIR/$LAST_CAPTURE_DIR"
  fi
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
    # Check if job exists
    if ! check_job_exists; then
      echo "Job $JOB_NAME was deleted at $(date)" >> "$LOG_DIR/status.log"
      break
    fi

    # Check if job has errors
    if check_job_error; then
      echo "Job $JOB_NAME failed at $(date)" >> "$LOG_DIR/status.log"
      break
    fi

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