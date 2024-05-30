import os
import urllib3
import pandas as pd

from kubernetes import client, config

from fmperf import Cluster
from fmperf import TGISModelSpec, WorkloadSpec
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
        cluster = Cluster(name="llm", apiclient=apiclient, namespace=os.environ["OPENSHIFT_NAMESPACE"])
        model_pvcs = [("my-models-pvc", "/models")]
        workload_pvc_name = "my-workload-pvc"
        cluster_gpu_name = "NVIDIA-A100-SXM4-80GB"
    else:
        raise ValueError("Valid choices for model_mode are local and remote")

    return cluster, model_pvcs, workload_pvc_name, cluster_gpu_name


if __name__ == "__main__":
    cluster, model_pvcs, workload_pvc_name, cluster_gpu_name = initialize_kubernetes(
        "remote"
    )

    model_spec = TGISModelSpec(
        name="google/flan-t5-xl",
        dtype_str="float16",
        image="quay.io/wxpe/text-gen-server:main.9b4aea8",
        pvcs=model_pvcs,
        cluster_gpu_name=cluster_gpu_name,
    )

    workload_spec = HomogeneousWorkloadSpec.from_yaml("workload_specifications.yml")
    workload_spec.pvc_name = workload_pvc_name

    # Prometheus URL and (if needed) token
    prom_url = "https://XXXXXX/api/v1/query_range"
    prom_token = ""

    # deploy model
    model = cluster.deploy_model(model_spec)

    # generate workload
    workload = cluster.generate_workload(model, workload_spec)

    print(workload.file)

    # sweep users
    df, edf = None, None
    for num_users in [1, 2, 4]:
        perf_out, energy_out = cluster.evaluate(
            model,
            workload,
            num_users=num_users,
            duration="2m",
            prom_url=prom_url,
            prom_token=prom_token,
        )

        perf_out = pd.DataFrame.from_records(perf_out, index="timestamp")
        energy_out = pd.DataFrame.from_dict(energy_out)

        # calculate latency, throughput, energy
        perf_out["n_tokens"] = perf_out["n_tokens"].astype("int64")
        tot_token_cnt = perf_out["n_tokens"].sum()
        if len(energy_out) > 0:
            energy_per_token = energy_out["energy"] / tot_token_cnt
        else:
            energy_per_token = pd.Series(np.nan)
        media_latency = perf_out["duration_ms"].median()
        p99_latency = perf_out["duration_ms"].quantile(0.99)
        throughput = tot_token_cnt / (perf_out["duration_ms"].sum() / 1000)
        res = pd.DataFrame(
            {
                "num_users": num_users,
                "median_lat": media_latency,
                "p99_lat": media_latency,
                "throughput": throughput,
                "energy_per_token": energy_per_token,
            }
        )
        print(res)

        # save results to output dataframe
        output_df = pd.concat([output_df, res], ignore_index=True)

    print(output_df)
    cluster.delete_model(model)
