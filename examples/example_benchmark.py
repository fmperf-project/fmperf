"""
This script runs benchmarking on TGIS server.
"""

import os
from pathlib import Path
import uuid

import kubernetes
import urllib3
from kubernetes import client, config

from fmperf import Cluster, TGISModelSpec, HomogeneousWorkloadSpec
from fmperf.utils import run_benchmark


# Initialize Kubernetes Configuration
def initialize_kubernetes(location):
    if location == "local":
        kubernetes.config.load_kube_config()
        apiclient = client.ApiClient()
        cluster = Cluster(name=location, apiclient=apiclient, namespace="default")
        model_pvcs = None
        workload_pvc_name = None
        cluster_gpu_name = None
    elif location == "remote":
        config = client.Configuration()
        config.host = os.environ["OPENSHIFT_HOST"]
        config.api_key_prefix["authorization"] = "Bearer"
        config.api_key["authorization"] = os.environ["OPENSHIFT_TOKEN"]
        config.verify_ssl = False
        apiclient = client.ApiClient(config)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        cluster = Cluster(
            name="llm", apiclient=apiclient, namespace=os.environ["OPENSHIFT_NAMESPACE"]
        )
        model_pvcs = [("my-models-pvc", "/models")]
        workload_pvc_name = "my-workload-pvc"
        cluster_gpu_name = "NVIDIA-A100-SXM4-80GB"
    else:
        raise ValueError("Valid choices for model_mode are local and remote")

    return cluster, model_pvcs, workload_pvc_name, cluster_gpu_name


if __name__ == "__main__":
    # USER Entry: Specify the deployment location [local or remote]
    LOCATION: str = "local"

    ## USER Entry: File Location for model parameters and workload parameters
    MODEL_FILE = "model_specifications_tgis_one.yml"
    WORKLOAD_FILE = "workload_specifications.yml"

    DURATION = "30s"  # Duration of experiment per each number of virtual users
    NUM_USERS = [1, 2]  # Number of virtual users creating requests
    REPETITION = 1  # Repeat the experiments this many times

    # Create a cluster object
    cluster, model_pvcs, workload_pvc_name, cluster_gpu_name = initialize_kubernetes(
        location=LOCATION
    )

    # Create workload object
    workload_spec = HomogeneousWorkloadSpec.from_yaml(WORKLOAD_FILE)
    workload_spec.pvc_name = workload_pvc_name

    # Create model object
    model_spec = TGISModelSpec.from_yaml(MODEL_FILE)
    model_spec.set_volumes(model_pvcs)
    model_spec.set_affinity(cluster_gpu_name)

    # Run benchmarking experiment with a unique id to avoid name collisions
    run_benchmark(
        cluster=cluster,
        model_spec=model_spec,
        workload_spec=workload_spec,
        repetition=REPETITION,
        number_users=NUM_USERS,
        duration=DURATION,
        id=str(uuid.uuid4())[:6],
    )
