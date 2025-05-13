#!/bin/bash

# Default values
NAMESPACE="vllm-prod"
PVC_NAME="workload-pvc"
LOCAL_DIR="./results"
POD_NAME="rsync-pod"
MOUNT_PATH="/data"
SOURCE_DIR=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -n|--namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    -p|--pvc)
      PVC_NAME="$2"
      shift 2
      ;;
    -d|--dir)
      LOCAL_DIR="$2"
      shift 2
      ;;
    -m|--mount-path)
      MOUNT_PATH="$2"
      shift 2
      ;;
    -s|--source-dir)
      SOURCE_DIR="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  -n, --namespace   OpenShift namespace (default: e2e-solution)"
      echo "  -p, --pvc        PVC name (default: workload-pvc)"
      echo "  -d, --dir        Local directory to sync to (default: ./results)"
      echo "  -m, --mount-path Mount path in the pod (default: /data)"
      echo "  -s, --source-dir Source directory inside the pod (default: root of mount path)"
      echo "  -h, --help       Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Create local directory if it doesn't exist
mkdir -p "$LOCAL_DIR"

# Create a pod with the PVC mounted
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: $POD_NAME
  namespace: $NAMESPACE
spec:
  containers:
  - name: rsync
    image: alpine:latest
    command: ["/bin/sh", "-c"]
    args: ["apk add --no-cache rsync && sleep infinity"]
    volumeMounts:
    - name: requests
      mountPath: $MOUNT_PATH
  volumes:
  - name: requests
    persistentVolumeClaim:
      claimName: $PVC_NAME
EOF

# Wait for the pod to be ready
echo "Waiting for pod to be ready..."
oc wait --for=condition=Ready pod/$POD_NAME -n $NAMESPACE

# Use rsync to copy files, excluding hf_cache and lost+found
echo "Syncing files from PVC to $LOCAL_DIR..."
if [ -z "$SOURCE_DIR" ]; then
    oc rsync $POD_NAME:$MOUNT_PATH/ "$LOCAL_DIR" -n $NAMESPACE --exclude="hf_cache" --exclude="vllm" --exclude="lost+found"
else
    oc rsync $POD_NAME:$MOUNT_PATH/$SOURCE_DIR/ "$LOCAL_DIR" -n $NAMESPACE --exclude="hf_cache" --exclude="vllm" --exclude="lost+found"
fi

# Clean up the temporary pod
echo "Cleaning up temporary pod..."
oc delete pod $POD_NAME -n $NAMESPACE

echo "Done! Files have been synced to $LOCAL_DIR" 
