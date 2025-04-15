import yaml
import requests
import time
from typing import Optional

class StackSpec:
    """
    Class for different LLM deployment stack specifications that provide OpenAI-compatible APIs
    """
    def __init__(
        self,
        name: str,
        stack_type: str,  # "aibrix", "dynamo", "vllm-prod", "custom"
        endpoint_url: str = None,
        api_key: str = None,
        api_version: str = None,
        models: list[str] = None,
        router_port: int = 8000,
        health_check_path: str = "/health",
        timeout: int = 600,
        refresh_interval: int = 300,  # 5 minutes default refresh interval
    ):
        self.name = name
        self.stack_type = stack_type.lower()
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.api_version = api_version
        self.models = models or []
        self.router_port = router_port
        self.health_check_path = health_check_path
        self.timeout = timeout
        self.refresh_interval = refresh_interval
        self.last_refresh = 0  # timestamp of last refresh

        # Set default configurations based on stack type
        self._configure_stack()

    def _configure_stack(self):
        """Configure stack-specific defaults"""
        if self.stack_type == "aibrix":
            if not self.endpoint_url:
                self.endpoint_url = "http://aibrix-router:8000"
            if not self.health_check_path:
                self.health_check_path = "/v1/health"
            if not self.api_version:
                self.api_version = "v1"

        elif self.stack_type == "dynamo":
            if not self.endpoint_url:
                self.endpoint_url = "http://dynamo-router:8000"
            if not self.health_check_path:
                self.health_check_path = "/health"

        elif self.stack_type == "vllm-prod":
            if not self.endpoint_url:
                # Use the in-cluster service name and port
                self.endpoint_url = "http://vllm-router-service:80"
            if not self.health_check_path:
                self.health_check_path = "/health"

    def get_service_url(self) -> str:
        """Get the service endpoint URL"""
        return self.endpoint_url

    def get_chat_completion_url(self) -> str:
        """Get the chat completion endpoint"""
        base = self.get_service_url()
        if self.stack_type in ["aibrix", "vllm-prod", "dynamo"]:
            return f"{base}/v1/chat/completions"
        return f"{base}/chat/completions"  # default path

    def get_completion_url(self) -> str:
        """Get the completion endpoint"""
        base = self.get_service_url()
        if self.stack_type in ["aibrix", "vllm-prod", "dynamo"]:
            return f"{base}/v1/completions"
        return f"{base}/completions"  # default path

    def get_models_url(self) -> str:
        """Get the models list endpoint"""
        base = self.get_service_url()
        if self.stack_type in ["aibrix", "vllm-prod", "dynamo"]:
            return f"{base}/v1/models"
        return f"{base}/models"  # default path

    def get_headers(self) -> dict:
        """Get the required headers for API calls"""
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_health_check_url(self) -> str:
        """Get the health check endpoint"""
        base = self.get_service_url()
        return f"{base}{self.health_check_path}"

    def refresh_models(self, force: bool = False) -> Optional[list[str]]:
        """
        Refresh the list of available models from the stack's models endpoint.
        
        Args:
            force: If True, refresh regardless of the refresh interval
            
        Returns:
            List of model names if refresh was successful, None if skipped due to refresh interval
        """
        current_time = time.time()
        if not force and (current_time - self.last_refresh) < self.refresh_interval:
            return None

        try:
            response = requests.get(
                self.get_models_url(),
                headers=self.get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract model names from the response
            # OpenAI API format: {"data": [{"id": "model1"}, {"id": "model2"}]}
            if "data" in data and isinstance(data["data"], list):
                self.models = [model["id"] for model in data["data"]]
            else:
                # Fallback for non-standard API responses
                self.models = [str(model) for model in data]
                
            self.last_refresh = current_time
            return self.models
            
        except Exception as e:
            print(f"Failed to refresh models list: {str(e)}")
            return None

    @classmethod
    def from_yaml(cls, file: str):
        """Create stack spec from YAML configuration"""
        with open(file, "r") as f:
            config = yaml.safe_load(f)
        return cls(**config)

    def to_yaml(self, file: str):
        """Save stack spec to YAML configuration"""
        config = {
            "name": self.name,
            "stack_type": self.stack_type,
            "endpoint_url": self.endpoint_url,
            "api_key": self.api_key,
            "api_version": self.api_version,
            "models": self.models,
            "router_port": self.router_port,
            "health_check_path": self.health_check_path,
            "timeout": self.timeout,
            "refresh_interval": self.refresh_interval
        }
        with open(file, "w") as f:
            yaml.dump(config, f) 