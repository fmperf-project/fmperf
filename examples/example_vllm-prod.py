"""
This script runs benchmarking on an existing vllm-prod stack deployment.
"""

import os
import urllib3

import kubernetes
from kubernetes import client, config

from fmperf import Cluster
from fmperf import HomogeneousWorkloadSpec
from fmperf.StackSpec import StackSpec
from fmperf.utils import run_benchmark
from fmperf.utils.storage import create_local_storage


# Initialize Kubernetes Configuration
def initialize_kubernetes(location):
    if location == "local":
        kubernetes.config.load_kube_config()
        apiclient = client.ApiClient()
        cluster = Cluster(name=location, apiclient=apiclient, namespace="default")
        
        # Create local storage for workload data
        _, workload_pvc_name = create_local_storage(
            apiclient=apiclient,
            namespace="default",
            host_path="/requests"
        )
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
        workload_pvc_name = "my-workload-pvc"
    else:
        raise ValueError("Valid choices for model_mode are local and remote")

    return cluster, workload_pvc_name


if __name__ == "__main__":
    # USER Entry: Specify the deployment location [local or remote]
    LOCATION: str = "local"

    ## USER Entry: File Location for model workload parameters
    WORKLOAD_FILE = os.path.join(os.path.dirname(__file__), "workload_specification.yml")

    # Initialize Kubernetes
    cluster, workload_pvc_name = initialize_kubernetes(LOCATION)

    # Create workload object
    workload_spec = HomogeneousWorkloadSpec.from_yaml(WORKLOAD_FILE)
    workload_spec.pvc_name = workload_pvc_name

    # Create stack spec for the existing vllm-prod deployment
    stack_spec = StackSpec(
        name="vllm-prod-stack",
        stack_type="vllm-prod",  # This will automatically set endpoint to vllm-router-service
        refresh_interval=300  # Refresh model list every 5 minutes
    )

    # Refresh the list of available models
    available_models = stack_spec.refresh_models(force=True)
    if available_models:
        print(f"Available models in the stack: {available_models}")
    else:
        print("Warning: Could not fetch available models from the stack")

    # USER Entry: Experiment variables
    DURATION = "30s"  # Duration of inference experiment
    NUM_USERS = [1, 2]  # Number of virtual users creating requests
    REPETITION = 1  # Repeat the experiments this many times

    # Run benchmarking experiment against the stack
    run_benchmark(
        cluster=cluster,
        stack_spec=stack_spec,  # Using stack_spec instead of model_spec
        workload_spec=workload_spec,
        repetition=REPETITION,
        number_users=NUM_USERS,
        duration=DURATION,
    ) 