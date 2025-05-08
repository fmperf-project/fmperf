"""
This script runs benchmarking on an existing llm-d stack deployment using LMBenchmark workload.
Note: When using LMBenchmarkWorkload, only the repetition parameter is used.
The duration and number_users parameters are ignored as the workload specification
controls these through max_requests and max_seconds.
"""

import os
import urllib3

import kubernetes
from kubernetes import client, config

from fmperf import Cluster
from fmperf import LMBenchmarkWorkload
from fmperf.StackSpec import StackSpec
from fmperf.utils import run_benchmark
from fmperf.utils.storage import create_local_storage, create_vpc_block_storage


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
            host_path="/results"  # Using /results for LMBenchmark
        )
    elif location == "remote":
        config = client.Configuration()
        config.host = os.environ.get("FMPERF_OPENSHIFT_HOST")
        config.api_key_prefix["authorization"] = "Bearer"
        config.api_key["authorization"] = os.environ.get("FMPERF_OPENSHIFT_TOKEN")
        config.verify_ssl = False
        apiclient = client.ApiClient(config)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        cluster = Cluster(
            name="llm", apiclient=apiclient, namespace=os.environ.get("FMPERF_OPENSHIFT_NAMESPACE")
        )
        
        # Create PVC using VPC Block Storage for remote deployment
        workload_pvc_name = create_vpc_block_storage(
            apiclient=apiclient,
            namespace=os.environ.get("FMPERF_OPENSHIFT_NAMESPACE"),
            storage_class=os.environ.get("FMPERF_OPENSHIFT_STORAGECLASS", "nfs-client-pokprod")
        )
    else:
        raise ValueError("Valid choices for model_mode are local and remote")

    return cluster, workload_pvc_name


if __name__ == "__main__":
    # USER Entry: Specify the deployment location [local or remote]
    LOCATION: str = "remote"

    ## USER Entry: File Location for model workload parameters
    default_yaml_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yamls")
    yaml_filename = os.environ.get("FMPERF_WORKLOAD_FILE", "lmbench_llama70b_2replica_H100.yaml")
    WORKLOAD_FILE = os.path.join(default_yaml_dir, yaml_filename)

    # Initialize Kubernetes
    cluster, workload_pvc_name = initialize_kubernetes(LOCATION)

    # Create workload object
    workload_spec = LMBenchmarkWorkload.from_yaml(WORKLOAD_FILE)
    workload_spec.pvc_name = workload_pvc_name

    # Create stack spec for the existing vllm-d deployment
    stack_spec = StackSpec(
        name=os.environ.get("FMPERF_STACK_NAME", "llm-d-70b-2replicas-H100"),
        stack_type=os.environ.get("FMPERF_STACK_TYPE", "llm-d"),  # This will automatically set endpoint to vllm-router-service
        refresh_interval=300,  # Refresh model list every 5 minutes
        endpoint_url=os.environ.get("FMPERF_ENDPOINT_URL", "inference-gateway")  # Service name
    )

    # USER Entry: Experiment variables
    # Note: For LMBenchmarkWorkload, only repetition is used
    # duration and number_users are controlled by the workload spec
    REPETITION = 1  # Repeat the experiments this many times

    # Run benchmarking experiment against the stack
    run_benchmark(
        cluster=cluster,
        stack_spec=stack_spec,  # Using stack_spec instead of model_spec
        workload_spec=workload_spec,
        repetition=REPETITION,
    ) 
