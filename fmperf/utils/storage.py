import kubernetes
from kubernetes import client
from typing import Tuple

def create_local_storage(
    apiclient: client.ApiClient,
    namespace: str = "default",
    pv_name: str = "fmperf-workload-pv",
    pvc_name: str = "fmperf-workload-pvc",
    host_path: str = "/requests",
    storage_size: str = "1Gi"
) -> Tuple[str, str]:
    """
    Create a local PersistentVolume and PersistentVolumeClaim for workload data.
    
    Args:
        apiclient: Kubernetes API client
        namespace: Namespace for the PVC
        pv_name: Name of the PersistentVolume
        pvc_name: Name of the PersistentVolumeClaim
        host_path: Local path to mount
        storage_size: Size of the storage
        
    Returns:
        Tuple of (pv_name, pvc_name)
    """
    # Create PV
    try:
        # Check if PV already exists
        apiclient.call_api(
            f"/api/v1/persistentvolumes/{pv_name}",
            "GET"
        )
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            # Create PV if it doesn't exist
            pv = {
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "metadata": {
                    "name": pv_name
                },
                "spec": {
                    "capacity": {
                        "storage": storage_size
                    },
                    "accessModes": ["ReadWriteMany"],
                    "hostPath": {
                        "path": host_path,
                        "type": "DirectoryOrCreate"
                    },
                    "persistentVolumeReclaimPolicy": "Retain",
                    "storageClassName": "manual"
                }
            }
            apiclient.call_api(
                "/api/v1/persistentvolumes",
                "POST",
                body=pv
            )
    
    # Create PVC
    try:
        # Check if PVC already exists
        apiclient.call_api(
            f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{pvc_name}",
            "GET"
        )
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            # Create PVC if it doesn't exist
            pvc = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": pvc_name,
                    "namespace": namespace
                },
                "spec": {
                    "accessModes": ["ReadWriteMany"],
                    "resources": {
                        "requests": {
                            "storage": storage_size
                        }
                    },
                    "storageClassName": "manual",
                    "volumeName": pv_name
                }
            }
            apiclient.call_api(
                f"/api/v1/namespaces/{namespace}/persistentvolumeclaims",
                "POST",
                body=pvc
            )
    
    return pv_name, pvc_name

def delete_local_storage(
    apiclient: client.ApiClient,
    namespace: str = "default",
    pv_name: str = "fmperf-workload-pv",
    pvc_name: str = "fmperf-workload-pvc"
) -> None:
    """
    Delete the local PersistentVolume and PersistentVolumeClaim.
    
    Args:
        apiclient: Kubernetes API client
        namespace: Namespace for the PVC
        pv_name: Name of the PersistentVolume
        pvc_name: Name of the PersistentVolumeClaim
    """
    try:
        # Delete PVC
        apiclient.call_api(
            f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{pvc_name}",
            "DELETE"
        )
    except kubernetes.client.rest.ApiException:
        pass
    
    try:
        # Delete PV
        apiclient.call_api(
            f"/api/v1/persistentvolumes/{pv_name}",
            "DELETE"
        )
    except kubernetes.client.rest.ApiException:
        pass 