#!/bin/bash

# Default values
NAMESPACE="e2e-solution"
PVC_NAME="workload-pvc"
LOCAL_DIR="./results"
POD_NAME="rsync-pod"

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
    -h|--help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  -n, --namespace   OpenShift namespace (default: vllm-prod)"
      echo "  -p, --pvc        PVC name (default: workload-pvc)"
      echo "  -d, --dir        Local directory to sync to (default: ./results)"
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
    image: busybox
    command: ["sleep", "infinity"]
    volumeMounts:
    - name: requests
      mountPath: /requests
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
oc rsync $POD_NAME:/requests/ "$LOCAL_DIR" -n $NAMESPACE --exclude="hf_cache" --exclude="lost+found"

# Clean up the temporary pod
echo "Cleaning up temporary pod..."
oc delete pod $POD_NAME -n $NAMESPACE

echo "Done! Files have been synced to $LOCAL_DIR" 