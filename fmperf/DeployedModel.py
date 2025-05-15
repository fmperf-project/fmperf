from typing import Union
from fmperf.ModelSpecs import ModelSpec
from fmperf.StackSpec import StackSpec


class DeployedModel:
    def __init__(self, spec: Union[ModelSpec, StackSpec], name: str, url: str):
        """Initialize a deployed model or stack.

        Args:
            spec: Either a ModelSpec for individual model deployments or StackSpec for existing stacks
            name: Name of the deployment
            url: Service URL for the deployment
        """
        self.spec = spec
        self.name = name
        self.url = url 