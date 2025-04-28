"""
This script runs benchmarking on TGIS or vLLM server.
"""

import os
import urllib3

import kubernetes
from kubernetes import client, config

from fmperf import Cluster
from fmperf import TGISModelSpec, vLLMModelSpec, HomogeneousWorkloadSpec
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

    # USER Entry: Specify the inference service [tgis or vllm]
    SERVER_TYPE: str = "vllm"

    ## USER Entry: File Location for model workload parameters
    WORKLOAD_FILE = "workload_specification.yml"

    # Initialize Kubernetes
    cluster, model_pvcs, workload_pvc_name, cluster_gpu_name = initialize_kubernetes(
        LOCATION
    )

    # Create workload object
    workload_spec = HomogeneousWorkloadSpec.from_yaml(WORKLOAD_FILE)
    workload_spec.pvc_name = workload_pvc_name

    if SERVER_TYPE == "tgis":
        model_spec = TGISModelSpec(
            name="gpt2",
            dtype_str="float16",
            image="quay.io/wxpe/text-gen-server:main.9b4aea8",
            pvcs=model_pvcs,
            cluster_gpu_name=cluster_gpu_name,
        )

    elif SERVER_TYPE == "vllm":
        model_spec = vLLMModelSpec(
            name="gpt2",
            dtype="float16",
            image="vllm/vllm-openai:latest",
            pvcs=model_pvcs,
            cluster_gpu_name=cluster_gpu_name,
        )

    else:
        raise ValueError("Valid choices for SERVER_TYPE are 'tgis' OR 'vllm']")

    # USER Entry: Experiment variables
    DURATION = "30s"  # Duration of inference experiment
    NUM_USERS = [1, 2]  # Number of virtual users creating requests
    REPETITION = 1  # Repeat the experimnts this many times

    # Run benchmarking experiment
    run_benchmark(
        cluster=cluster,
        model_spec=model_spec,
        workload_spec=workload_spec,
        repetition=REPETITION,
        number_users=NUM_USERS,
        duration=DURATION,
    )
