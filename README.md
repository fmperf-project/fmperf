# fmperf

The repository contains code for `fmperf` (foundation model performance), a Python-based benchmarking tool for large language models (LLM) serving frameworks.
Currently it can be used to evaluate the **performance and energy efficiency** of [TGIS](https://github.com/IBM/text-generation-inference) and [vLLM](https://github.com/vllm-project/vllm) inference servers.

The high-level architecture of the benchmark is illustrated below.
The python module `fmperf` can be used to specify and orchestrate benchmarking experiments.
All experiments are executed on a Kubernetes (k8s) or OpenShift cluster, and `fmperf` uses the Python k8s client to orchestrate the different components.
Specifically, `fmperf` provides a simple Python API for deploying an inference server as a k8s `Deployment` and `Service`.
Additionally, APIs are provided for creating a k8s `Job` to perform load testing of the service (`fmperf.loadgen`).

<img width="779" alt="image" src="https://github.com/fmperf-project/fmperf/assets/7945038/dd68109b-95f3-4d11-b8aa-244d35a8dd7c">

## Setup

The benchmark runs on your laptop or development machine, but needs to be pointed to a k8s or OpenShift cluster where the experiments will be run.
This may be a `remote cluster`, or it could be a `local k8s cluster` in your development machine. For full instructions on bringing up a local k8s cluster please see our documentation [here](docs/SETUP.md).

In order to use `fmperf`, we need to clone the repo and create a conda environment with necessary dependencies:
```shell
git clone https://github.com/fmperf-project/fmperf
cd fmperf
conda create -y -n fmperf-env python=3.11
conda activate fmperf-env
pip install -r requirements.txt
pip install -e .
```

## Usage

Examples of how use use `fmperf` as a library can be found in the `examples` directory. The directory comprises various python scripts performing the benchmarking experiments. Please see our documentation [here](/examples/README.md).

## Load testing

It is also possible to use the load testing functionaltiy of `fmperf` independently of the OpenShift orchestration layer.
In this scenario, you can build the docker container and then configure it via a `.env` file to point at an inference server
that you have deployed locally (or remotely).

Build docker image using the Dockerfile:

```
docker build -t fmperf .
```

Create environment file and populate with desired configuration:
```bash
cp .env.example .env
```

The benchmark needs to create a large file containing many heterogeneous requests.
Rather than create this file each time, it is recommended to persist this file.
To do this we will create a directory on the host that the container will write to:
```bash
mkdir requests
chmod o+w requests
```
Then we run the container to generate the sample requests. There are two ways this can be done currently.
Firstly, one can generate a set of requests assuming simple uniform distributions for parameters like number of input/output tokens:
```bash
docker run --env-file .env -it --rm -v $(pwd)/requests:/requests fmperf python -m fmperf.loadgen.generate-input
```
Alternatively, one can generate a set of requests using models that have been trained on requests sent to a production deployment:
```bash
docker run --env-file .env -it --rm -v $(pwd)/requests:/requests fmperf python -m fmperf.loadgen.generate-input --from-model
```
**Important Note**: if generating inputs for vLLM, it is also necessary to add another `-v` argument to mount the folder where the model weights
reside (in exactly the same way they are mounted inside the inference server image). This is required because it is necessary to perform tokenization
inside the fmperf image until vLLM PR [3144](https://github.com/vllm-project/vllm/pull/3144) is merged.

Once the requests have been generated, we can run an experiment for a fixed number of virtual users (controlled via the `NUM_USERS` env variable) by running the container as follows:
```bash
docker run --env-file .env -it --rm -v $(pwd)/requests:/requests fmperf python -m fmperf.loadgen.run
```
Finally, we can run a sweep over different number of virtual users (controlled via the `SWEEP_USERS` env variable) as follows:
```bash
docker run --env-file .env -it --rm -v $(pwd)/requests:/requests fmperf python -m fmperf.loadgen.sweep
```

## Getting Help

If you need help using the framework encounter issues please open an issue directly on this repo.
