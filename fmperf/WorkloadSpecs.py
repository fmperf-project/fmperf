import yaml
import os
import json
from typing import Union
from fmperf.Cluster import DeployedModel
from fmperf.StackSpec import StackSpec


class WorkloadSpec:
    def __init__(
        self,
        sample_size: int = 10,
        image: str = "quay.io/fmperf/fmperf:main",
        pvc_name: str = None,
        overwrite: bool = False,
    ):
        self.sample_size = sample_size
        self.image = image
        self.pvc_name = pvc_name
        self.overwrite = overwrite

    @classmethod
    def from_yaml(cls, file: str):
        """
        The function processes the yaml file to create workload specs
        """
        with open(file, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def get_env(
        self,
        target: str,
        model: Union["DeployedModel", "StackSpec"],
        outfile: str,
    ):
        if isinstance(model, DeployedModel):
            model_id = model.spec.name
            model_url = model.url
        else:
            model_id = self.model_name if hasattr(self, 'model_name') else model.get_available_models()[0]
            model_url = model.get_service_url()

        env = [
            {"name": "TARGET", "value": target},
            {"name": "MODEL_ID", "value": model_id},
            {
                "name": "SAMPLE_SIZE",
                "value": str(self.sample_size),
            },
            {
                "name": "URL",
                "value": model_url,
            },
            {
                "name": "OVERWRITE",
                "value": str(self.overwrite),
            },
            {"name": "REQUESTS_FILENAME", "value": outfile},
            {"name": "WORKLOAD_DIR", "value": "/requests"},
            {"name": "HF_HOME", "value": "/tmp/hf_cache"},
        ]
        
        # Add Hugging Face token if available in the environment
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("hf_token") or os.environ.get("huggingface_token")
        if hf_token:
            env.append({"name": "HUGGINGFACE_TOKEN", "value": hf_token})
            env.append({"name": "HF_TOKEN", "value": hf_token})
            
        return env


class HomogeneousWorkloadSpec(WorkloadSpec):
    def __init__(
        self,
        input_tokens: int = 500,
        output_tokens: int = 50,
        greedy: bool = True,
        image: str = "fmperf-project/fmperf:local",
        pvc_name: str = None,
        overwrite: bool = False,
        model_name: str = None,
    ):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.greedy = greedy
        self.model_name = model_name

        super().__init__(1, image, pvc_name, overwrite)

    @classmethod
    def from_yaml(cls, file: str):
        return super().from_yaml(file)

    def get_args(self):
        return ["python -m fmperf.loadgen.generate-input"]

    def get_env(
        self,
        target: str,
        model: Union["DeployedModel", "StackSpec"],
        outfile: str,
    ):
        env = super().get_env(target, model, outfile) + [
            {
                "name": "MIN_INPUT_TOKENS",
                "value": str(self.input_tokens),
            },
            {
                "name": "MAX_INPUT_TOKENS",
                "value": str(self.input_tokens),
            },
            {
                "name": "MIN_OUTPUT_TOKENS",
                "value": str(self.output_tokens),
            },
            {
                "name": "MAX_OUTPUT_TOKENS",
                "value": str(self.output_tokens),
            },
            {
                "name": "FRAC_GREEDY",
                "value": "1.0" if self.greedy else "0.0",
            },
        ]
        if self.model_name:
            env.append({
                "name": "MODEL_NAME",
                "value": self.model_name,
            })
        return env


class HeterogeneousWorkloadSpec(WorkloadSpec):
    def __init__(
        self,
        min_input_tokens: int = 10,
        max_input_tokens: int = 20,
        min_output_tokens: int = 10,
        max_output_tokens: int = 20,
        frac_greedy: float = 0.5,
        sample_size: int = 10,
        image: str = "quay.io/fmperf/fmperf:main",
        pvc_name: str = None,
        overwrite: bool = False,
        model_name: str = None,
    ):
        self.min_input_tokens = min_input_tokens
        self.max_input_tokens = max_input_tokens
        self.min_output_tokens = min_output_tokens
        self.max_output_tokens = max_output_tokens
        self.frac_greedy = frac_greedy
        self.model_name = model_name
        super().__init__(sample_size, image, pvc_name, overwrite)

    @classmethod
    def from_yaml(cls, file: str):
        return super().from_yaml(file)

    def get_args(self):
        return ["python -m fmperf.loadgen.generate-input"]

    def get_env(
        self,
        target: str,
        model: "DeployedModel",
        outfile: str,
    ):
        env = super().get_env(target, model, outfile) + [
            {
                "name": "MIN_INPUT_TOKENS",
                "value": str(self.min_input_tokens),
            },
            {
                "name": "MAX_INPUT_TOKENS",
                "value": str(self.max_input_tokens),
            },
            {
                "name": "MIN_OUTPUT_TOKENS",
                "value": str(self.min_output_tokens),
            },
            {
                "name": "MAX_OUTPUT_TOKENS",
                "value": str(self.max_output_tokens),
            },
            {
                "name": "FRAC_GREEDY",
                "value": str(self.frac_greedy),
            },
        ]
        if self.model_name:
            env.append({
                "name": "MODEL_NAME",
                "value": self.model_name,
            })
        return env


class RealisticWorkloadSpec(WorkloadSpec):
    def __init__(
        self,
        sample_size: int = 10,
        image: str = "quay.io/fmperf/fmperf:main",
        pvc_name: str = None,
        overwrite: bool = False,
    ):
        super().__init__(sample_size, image, pvc_name, overwrite)

    @classmethod
    def from_yaml(cls, file: str):
        return super().from_yaml(file)

    def get_args(self):
        return ["python -m fmperf.loadgen.generate-input --from-model"]


class GuideLLMWorkloadSpec(WorkloadSpec):
    def __init__(
        self,
        model_name: str,
        rate_type: str = "sweep",
        prompt_tokens: int = 256,
        output_tokens: int = 128,
        max_requests: int = 100,
        max_seconds: int = 100,
        output_format: str = "json",
        image: str = "quay.io/chenw615/guidellm-benchmark:latest",
        pvc_name: str = None,
        overwrite: bool = False,
        hf_token: str = None,
        service_account: str = None,
    ):
        self.model_name = model_name
        self.rate_type = rate_type
        self.prompt_tokens = prompt_tokens
        self.output_tokens = output_tokens
        self.max_requests = max_requests
        self.max_seconds = max_seconds
        self.output_format = output_format
        self.hf_token = hf_token
        self.service_account = service_account
        super().__init__(1, image, pvc_name, overwrite)

    @classmethod
    def from_yaml(cls, file: str):
        return super().from_yaml(file)

    def get_args(self):
        return []

    def get_env(
        self,
        target: str,
        model: Union["DeployedModel", "StackSpec"],
        outfile: str,
    ):
        # Get the model URL based on the model type
        if isinstance(model, DeployedModel):
            model_url = model.url
        else:
            model_url = model.get_service_url()
            
        # Ensure model_url has http:// prefix
        if not model_url.startswith(('http://', 'https://')):
            model_url = f"http://{model_url}"

        env = [
            {"name": "TARGET", "value": model_url},
            {"name": "MODEL", "value": self.model_name},
            {"name": "RATE_TYPE", "value": self.rate_type},
            {"name": "DATA", "value": f"prompt_tokens={self.prompt_tokens},output_tokens={self.output_tokens}"},
            {"name": "MAX_REQUESTS", "value": str(self.max_requests)},
            {"name": "MAX_SECONDS", "value": str(self.max_seconds)},
            {"name": "OUTPUT_FORMAT", "value": self.output_format},
        ]
        
        # Add Hugging Face token if available
        print("Checking for HF_TOKEN...")
        print(f"self.hf_token: {self.hf_token}")
        print(f"HF_TOKEN env: {os.environ.get('HF_TOKEN')}")
        print(f"HUGGINGFACE_TOKEN env: {os.environ.get('HUGGINGFACE_TOKEN')}")
        print(f"hf_token env: {os.environ.get('hf_token')}")
        print(f"huggingface_token env: {os.environ.get('huggingface_token')}")
        
        hf_token = self.hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("hf_token") or os.environ.get("huggingface_token")
        if hf_token:
            print(f"Found HF_TOKEN: {hf_token}")
            env.append({"name": "HF_TOKEN", "value": hf_token})
        else:
            print("No HF_TOKEN found!")
            
        return env

class LMBenchmarkWorkload(WorkloadSpec):
    def __init__(
        self,
        model_name: str,
        base_url: str = None,
        scenarios: str = "sharegpt",
        qps_values: str = "0.5 0.67 0.84 1 1.17 1.34",  # Default QPS values as space-separated string
        image: str = "lmcache/lmcache-benchmark:latest",
        pvc_name: str = None,
        overwrite: bool = False,
        service_account: str = None,
        chat_template: str = None,
    ):
        self.model_name = model_name
        self.base_url = base_url
        self.scenarios = scenarios
        self.qps_values = qps_values
        self.service_account = service_account
        self.chat_template = chat_template
        super().__init__(1, image, pvc_name, overwrite)

    @classmethod
    def from_yaml(cls, file: str):
        return super().from_yaml(file)

    def get_args(self):
        return []

    def get_env(
        self,
        target: str,
        model: Union["DeployedModel", "StackSpec"],
        outfile: str,
    ):
        # Get the model URL based on the model type
        if isinstance(model, DeployedModel):
            model_url = model.url
            folder_name = model.name
        else:
            # Use base_url from workload config if available, otherwise use model's service URL
            model_url = self.base_url if self.base_url else model.get_service_url()
            print(f"LMBenchmarkWorkload.get_env: model_url = {model_url}")
            folder_name = model.name
            
        # Ensure model_url has http:// prefix
        if not model_url.startswith(('http://', 'https://')):
            model_url = f"http://{model_url}"
            print(f"LMBenchmarkWorkload.get_env: model_url after http prefix = {model_url}")

        env = [
            {"name": "MODEL", "value": self.model_name},
            {"name": "BASE_URL", "value": model_url},
            {"name": "SAVE_FILE_KEY", "value": f"/requests/{folder_name}/LMBench"},
            {"name": "SCENARIOS", "value": self.scenarios},
        ]
        
        # Split QPS values and add them as individual environment variables
        qps_values = self.qps_values.split()
        for i, qps in enumerate(qps_values):
            env.append({"name": f"QPS_VALUES_{i}", "value": qps})
        
        if self.chat_template:
            # Pass chat template as a JSON string to be parsed by the script
            env.append({
                "name": "CHAT_TEMPLATE",
                "value": json.dumps({
                    "template": self.chat_template,
                    "use_template": True
                })
            })
            
        return env

