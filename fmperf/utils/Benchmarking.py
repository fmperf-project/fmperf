import pandas as pd
import os
from typing import List, Optional, Union

from fmperf import Cluster
from fmperf.ModelSpecs import ModelSpec
from fmperf.StackSpec import StackSpec
from fmperf.DeployedModel import DeployedModel
from fmperf.WorkloadSpecs import WorkloadSpec, GuideLLMWorkloadSpec
from fmperf.utils import parse_results


def _run_benchmark_iteration(cluster, model, workload, workload_spec, number_users, duration, id, rep):
    """Helper function to run a single benchmark iteration."""
    print(f"Performing sweep with {workload.file}")
    results = []
    
    if isinstance(workload_spec, GuideLLMWorkloadSpec):
        output, _ = cluster.evaluate(
            model,
            workload,
            num_users=1,  # Dummy value, not used
            duration="1s",  # Dummy value, not used
            id=id,
        )
        if output is not None:
            results.extend(output)
    else:
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
    
    if len(results) > 0:
        df = parse_results(results, print_df=True)
        df.to_csv(f"fmperf-{id}-result{rep}.csv")


# Run benchmark for models or stack deployment
def run_benchmark(
    cluster: Cluster,
    model_spec: Optional[List[ModelSpec]] = None,
    stack_spec: Optional[StackSpec] = None,
    workload_spec: WorkloadSpec = None,
    repetition: int = 1,
    number_users: Optional[Union[int, List[int]]] = 1,
    duration: Optional[str] = "10s",
    id: str = "",
) -> None:
    """Run benchmarking against either a model deployment or an existing stack deployment.
    
    Args:
        cluster: The cluster to run benchmarks on
        model_spec: List of ModelSpecs to deploy and benchmark (mutually exclusive with stack_spec)
        stack_spec: Existing stack deployment to benchmark (mutually exclusive with model_spec)
        workload_spec: The workload specification
        repetition: Number of times to repeat the benchmark
        number_users: Number of concurrent users (ignored for GuideLLMWorkloadSpec)
        duration: Duration of each benchmark run (ignored for GuideLLMWorkloadSpec)
        id: Optional identifier for the benchmark run
    """
    if model_spec is not None and stack_spec is not None:
        raise ValueError("Cannot specify both model_spec and stack_spec. Choose one.")
    if model_spec is None and stack_spec is None:
        raise ValueError("Must specify either model_spec or stack_spec.")

    id = cluster.generate_timestamp_id() if id == "" else id

    # Convert number_users to list if it's a single value
    if not isinstance(number_users, list):
        number_users = [number_users]

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
                    _run_benchmark_iteration(cluster, model, workload, workload_spec, number_users, duration, id, rep)
            finally:
                # Always clean up model deployment
                cluster.delete_model(model)
    else:
        # Handle stack case - no deployment needed
        stack_spec.refresh_models()
        # Run benchmarks directly with stack_spec
        workload = cluster.generate_workload(stack_spec, workload_spec, id=id)
        for rep in range(repetition):
            _run_benchmark_iteration(cluster, stack_spec, workload, workload_spec, number_users, duration, id, rep)
