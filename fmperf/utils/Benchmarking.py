import pandas as pd
import os
from typing import List, Optional

from fmperf import Cluster
from fmperf.ModelSpecs import ModelSpec
from fmperf.StackSpec import StackSpec
from fmperf.utils import parse_results
from fmperf.Cluster import DeployedModel


# Run benchmark for models or stack deployment
def run_benchmark(
    cluster: Cluster,
    model_spec: Optional[List[ModelSpec]] = None,
    stack_spec: Optional[StackSpec] = None,
    workload_spec: dict = None,
    repetition: int = 1,
    number_users: int = 1,
    duration: str = "10s",
    id: str = "",
) -> None:
    """Run benchmarking against either a model deployment or an existing stack deployment.
    
    Args:
        cluster: The cluster to run benchmarks on
        model_spec: List of ModelSpecs to deploy and benchmark (mutually exclusive with stack_spec)
        stack_spec: Existing stack deployment to benchmark (mutually exclusive with model_spec)
        workload_spec: The workload specification
        repetition: Number of times to repeat the benchmark
        number_users: Number of concurrent users
        duration: Duration of each benchmark run
        id: Optional identifier for the benchmark run
    """
    if model_spec is not None and stack_spec is not None:
        raise ValueError("Cannot specify both model_spec and stack_spec. Choose one.")
    if model_spec is None and stack_spec is None:
        raise ValueError("Must specify either model_spec or stack_spec.")

    if model_spec is not None:
        # Handle model deployment case
        if not isinstance(model_spec, list):
            model_spec = [model_spec]
            
        for spec in model_spec:
            # Deploy the model
            model = cluster.deploy_model(spec, id)
            try:
                # Run benchmarks
                workload = cluster.generate_workload(model, workload_spec, id=id)
                for rep in range(repetition):
                    print(f"Performing sweep with {workload.file}")
                    results = []
                    for num_users in number_users:
                        output, _ = cluster.evaluate(
                            model,
                            workload,
                            num_users=num_users,
                            duration=duration,
                            id=id,
                        )
                        if output is not None:
                            results.extend(output)
                    df = parse_results(results, print_df=True)
                    df.to_csv(os.path.join("/requests", f"result{rep}.csv"))
            finally:
                # Always clean up model deployment
                cluster.delete_model(model)
    else:
        # Handle stack case - no deployment needed
        model = DeployedModel(
            spec=stack_spec,
            name=stack_spec.name,
            url=stack_spec.get_service_url()
        )
        # Run benchmarks
        workload = cluster.generate_workload(model, workload_spec, id=id)
        for rep in range(repetition):
            print(f"Performing sweep with {workload.file}")
            results = []
            for num_users in number_users:
                output, _ = cluster.evaluate(
                    model,
                    workload,
                    num_users=num_users,
                    duration=duration,
                    id=id,
                )
                if output is not None:
                    results.extend(output)
            df = parse_results(results, print_df=True)
            df.to_csv(os.path.join("/requests", f"result{rep}.csv"))
