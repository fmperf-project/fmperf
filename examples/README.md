# Examples

## Structure (based on `example_benchmark.py`)

### Set the Kubernetes Configuration
Update the relevant sections under `if location == "local"` or `if location == "remote"` and set the appropriate value for `LOCATION` under `if __name__ == "__main__"`

### Initalize the Model Specification
There are two different ways to construct a model specification:

1. By calling the constructor of `TGISModelSpec` or `vLLMModelSpec` directly (as defined in [this file](/fmperf/ModelSpecs.py)).
2. By calling `TGISModelSpec.from_yaml` or `vLLMModelSpec.from_yaml` and passing a path to a YAML file defining the specification (see example [here](/examples/model_specifications_tgis_one.yml) for a `TGISModelSpec`). There is a one-to-one mapping between the constructor arguments and the key-value pairs in the yaml files.

### Initalize the Workload Specification
There are three different types of workloads to construct a workload specification from:

#### Homogeneous Workloads
Homogeneous workloads are workloads where all concurrent users of the inference server send the same request by calling the constructor `HomogeneousWorkloadSpec` (as defined in [this file](/fmperf/ModelSpecs.py)). The requests comprise the number of input tokens, output tokens, and a flag for greedy search. `workload_specifications.yaml` provides an example that is used for defining workload specifications in the python scripts provided in `/examples`. Here, there is a one-to-one mapping between the constructor arguments and the key-value pairs in the yaml files.

#### Heterogeneous Workloads
Heterogeneous workloads are workloads where all concurrent users of the inference server send different requests by calling the constructor `HeterogeneousWorkloadSpec` (as defined in [this file](/fmperf/ModelSpecs.py)),
with different number of input/output tokens. The user defines a range for input and output tokens using min/max values, and the requests are generated from an uniform distribution in
that range. The user can define the parameters in a yaml file or alternatively within the python scripts, as there is a one-to-one mapping between the constructor arguments and the key-value pairs in the yaml files.

#### Realistic Workloads
In this case, requests are generated using a statistical model that has been fitted to data from production logs by calling the constructor `RealisticWorkloadSpec` (as defined in [this file](/fmperf/ModelSpecs.py)).
Therefore, we can consider this a somewhat realistic internal workload. Here the user can define their model that can generate input and ouput tokens, and serialize them, for example into a pickle file.

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
