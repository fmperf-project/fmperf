#!/bin/bash

# Default values
NAMESPACE="e2e-solution"
PVC_NAME="workload-pvc"
POD_NAME="cleanup-pod"

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
    -h|--help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  -n, --namespace   OpenShift namespace (default: e2e-solution)"
      echo "  -p, --pvc        PVC name (default: workload-pvc)"
      echo "  -h, --help       Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Create a pod with the PVC mounted
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: $POD_NAME
  namespace: $NAMESPACE
spec:
  containers:
  - name: cleanup
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

# Execute cleanup command in the pod
echo "Cleaning up data from PVC..."
oc exec $POD_NAME -n $NAMESPACE -- sh -c 'cd /requests && find . -mindepth 1 -maxdepth 1 ! -name "hf_cache" ! -name "lost+found" -exec rm -rf {} +'

# Clean up the temporary pod
echo "Cleaning up temporary pod..."
oc delete pod $POD_NAME -n $NAMESPACE

echo "Done! Data has been cleaned from PVC while preserving hf_cache and lost+found folders" 