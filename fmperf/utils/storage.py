import kubernetes
from kubernetes import client
from typing import Tuple, Optional
import subprocess
import time

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

def create_cos_storage(
    apiclient: client.ApiClient,
    namespace: str,
    pvc_name: str = "workload-pvc",
    storage_size: str = "10Gi",
    storage_class: str = "ibmc-s3fs-cos"
) -> str:
    """
    Create a PersistentVolumeClaim using Cloud Object Storage (COS) for remote deployments.
    
    Args:
        apiclient: Kubernetes API client
        namespace: Namespace for the PVC
        pvc_name: Name of the PersistentVolumeClaim
        storage_size: Size of the storage
        storage_class: Storage class to use (default: ibmc-s3fs-cos)
        
    Returns:
        Name of the created PVC
    """
    pvc = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(
            name=pvc_name,
            namespace=namespace
        ),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteMany"],
            resources=client.V1ResourceRequirements(
                requests={"storage": storage_size}
            ),
            storage_class_name=storage_class
        )
    )
    
    try:
        v1 = client.CoreV1Api(apiclient)
        v1.create_namespaced_persistent_volume_claim(
            namespace=namespace,
            body=pvc
        )
    except client.exceptions.ApiException as e:
        if e.status == 409:  # PVC already exists
            pass
        else:
            raise e
    
    return pvc_name

def copy_from_pvc(
    namespace: str,
    pvc_name: str,
    local_path: str,
    pod_name: Optional[str] = None,
    container_path: str = "/data"
) -> None:
    """
    Copy data from a PVC to a local directory using oc rsync.
    
    Args:
        namespace: OpenShift namespace
        pvc_name: Name of the PVC
        local_path: Local directory to copy data to
        pod_name: Optional pod name to use for copying (if not provided, a temporary pod will be created)
        container_path: Path inside the container where the PVC is mounted
    """
    if pod_name is None:
        # Create a temporary pod to mount the PVC
        pod_name = f"rsync-{pvc_name}-pod"
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                namespace=namespace
            ),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name="rsync",
                        image="busybox",
                        command=["sleep", "infinity"],
                        volume_mounts=[
                            client.V1VolumeMount(
                                name="data",
                                mount_path=container_path
                            )
                        ]
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="data",
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name=pvc_name
                        )
                    )
                ]
            )
        )
        
        try:
            v1 = client.CoreV1Api()
            v1.create_namespaced_pod(namespace=namespace, body=pod)
            # Wait for pod to be ready
            while True:
                pod_status = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
                if pod_status.status.phase == "Running":
                    break
                time.sleep(1)
        except Exception as e:
            raise RuntimeError(f"Failed to create temporary pod: {str(e)}")
    
    try:
        # Use oc rsync to copy data
        cmd = [
            "oc", "rsync",
            f"{namespace}/{pod_name}:{container_path}/",
            local_path
        ]
        subprocess.run(cmd, check=True)
    finally:
        if pod_name.startswith("rsync-"):
            # Clean up temporary pod
            try:
                v1 = client.CoreV1Api()
                v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
            except Exception:
                pass 