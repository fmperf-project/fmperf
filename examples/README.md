# Examples

## Structure (based on `example_benchmark.py`)

### Set the Kubernetes Configuration
Update the relevant sections under `if location == "local"` or `if location == "remote"` and set the appropriate value for `LOCATION` under `if __name__ == "__main__"`

### Creating a Model Specification
There are two different ways to create a model specification:
1. By calling the constructor of `TGISModelSpec` or `vLLMModelSpec` directly (as defined in [this file](/fmperf/ModelSpecs.py)).
2. By calling `TGISModelSpec.from_yaml` or `vLLMModelSpec.from_yaml` and passing a path to a YAML file defining the specification (see example [here](/examples/model_specifications_tgis_one.yml) for a `TGISModelSpec`). 
There is a one-to-one mapping between the constructor arguments and the key-value pairs in the yaml files.

### Creating a Workload Specification
Similarly, one can create a workload specification by calling the constructor of one of the `WorkloadSpec` classes (as defined in [this file](/fmperf/ModelSpecs.py)) or by calling class method `from_yaml`. 
There are three different types of workloads that can be created:

#### Homogeneous Workloads
Homogeneous workloads are workloads where all concurrent users of the inference server send exactly the same request.
The corresponding class is `HomogeneousWorkloadSpec`.
When constructing a `HomogeneousWorkloadSpec`, one must define the number of input tokens (`input_tokens`), the number of output tokens (`output_tokens`) and whether the requests should use greedy sampling (`greedy`). 
An example YAML file is provided [here](/examples/workload_specification.yml).

#### Heterogeneous Workloads
Heterogeneous workloads are workloads where all concurrent users of the inference server send different requests.
The corresponding class is `HeterogeneousWorkloadSpec`.
When constructing a `HeterogeneousWorkloadSpec`, one must define a range for the number of input/output tokens using min/max values.
The number of input tokens for each request will be drawn uniformly between `min_input_tokens` and `max_input_tokens`. 
Similarly, the number of output tokens for each request will be drawn uniformly between `min_output_tokens` and `max_output_tokens`.
Similarly, whether each request will use greedy sampling is determined by sampling from a Bernoulli distribution with probability `frac_greedy`. 

#### Realistic Workloads
In this case, requests are generated using a statistical model that has been fitted to data from production logs.
The corresponding class is `RealisticWorkloadSpec`.
Please note that this feature is currently disabled, but will be enabled in the coming days.


### Execute `run_benchmark(...)` with the following parameters:
| Parameter     | Type                          | Definition                                                            |
|---------------|-------------------------------|-----------------------------------------------------------------------|
| cluster       | Object                        | Output of the Kubernetes Configuration                                |
| model_spec    | Object                        | Model specification                                                   |
| workload_spec | Object                        | Workload specification                                                |
| repetition    | Integer (e.g. 1)              | Number of times the experiment is to be repeated                      |
| number_users  | List of Integers (e.g [1, 2]) | Number of virtual concurrent users creating requests                  |
| duration      | String (e.g. "30s")           | Duration of experiment per each number of virtual concurrent users    |
| id            | Stringified UUID              | Unique identifier for the experiment                                  |
