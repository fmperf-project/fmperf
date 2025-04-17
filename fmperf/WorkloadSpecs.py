import yaml
import os
from typing import Union
from fmperf.Cluster import DeployedModel


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
