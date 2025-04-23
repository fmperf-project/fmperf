import hashlib
import json
import typing
from typing import Union
import os
from datetime import datetime

import pandas as pd
from kubernetes import client

from fmperf.ModelSpecs import ModelSpec, TGISModelSpec, vLLMModelSpec
from fmperf.StackSpec import StackSpec
from fmperf.DeployedModel import DeployedModel
from fmperf.utils import Creating, Deleting, Waiting, make_logger
from fmperf.WorkloadSpecs import WorkloadSpec, GuideLLMWorkloadSpec


class GeneratedWorkload:
    def __init__(self, spec: WorkloadSpec, file: str, target: str):
        self.spec = spec
        self.file = file
        self.target = target


class Cluster:
    def __init__(
        self, name: str, apiclient: client.ApiClient, namespace: str = "default"
    ):
        self.name = name
        self.apiclient = apiclient
        self.namespace = namespace
        self.logger = make_logger(self.name)

        self.security_context = {
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
            "runAsNonRoot": False,
            "runAsUser": 0,
            "seccompProfile": {"type": "RuntimeDefault"},
        }

    def generate_timestamp_id(self) -> str:
        """Generate an ID in the format YYYYMMDD-HHMM."""
        return datetime.now().strftime("%Y%m%d-%H%M")

    def apigetter(self):
        return self.apiclient

    def deploy_model(
        self,
        model: ModelSpec,
        id: str = "",
    ):
        creating = Creating(self.apigetter, self.logger, ignore_exists=True)
        vars = model.get_vars()

        if len(model.volumes) == 0:
            model.volumes = [
                {
                    "name": "models",
                    "hostPath": {
                        "path": "/models",
                    },
                },
                {
                    "name": "cache-volume",
                    "emptyDir": {
                        "medium": "Memory",
                        "sizeLimit": "1Gi",
                    },
                },
            ]
            model.volume_mounts = [
                {
                    "name": "models",
                    "mountPath": "/models",
                },
                {
                    "mountPath": "/dev/shm",
                    "name": "cache-volume",
                },
            ]

        if type(model) is TGISModelSpec:
            name = "fmperf-tgis-%s-server%s" % (
                model.shortname.replace(".", "-"),
                "-" + id if id else "",
            )
        elif type(model) is vLLMModelSpec:
            name = "fmperf-vllm-%s-server%s" % (
                model.shortname.replace(".", "-"),
                "-" + id if id else "",
            )
        else:
            raise TypeError("Unrecognized ModelSpec")

        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "labels": {"app": name},
                "name": name,
                "namespace": self.namespace,
            },
            "spec": {
                "serviceAccountName": "fmperf",
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "app": name,
                    }
                },
                "strategy": {"rollingUpdate": {"maxSurge": 1}},
                "template": {
                    "metadata": {
                        "annotations": {
                            "prometheus.io/port": "3000",
                            "prometheus.io/scrape": "true",
                        },
                        "labels": {
                            "app": name,
                        },
                    },
                    "spec": {
                        "affinity": model.affinity,
                        "containers": [
                            {
                                "env": vars,
                                "command": model.get_command(),
                                "args": model.get_args(),
                                "image": model.image,
                                "livenessProbe": model.get_liveness_probe(),
                                "name": "server",
                                "ports": model.get_ports(),
                                "readinessProbe": model.get_readiness_probe(),
                                "resources": {
                                    "limits": {
                                        "cpu": str(model.cpu_limit),
                                        "memory": model.memory_limit,
                                        "nvidia.com/gpu": str(model.num_gpus),
                                    },
                                    "requests": {"cpu": str(model.cpu_request)},
                                },
                                "securityContext": self.security_context,
                                "startupProbe": model.get_startup_probe(),
                                "volumeMounts": model.volume_mounts,
                            }
                        ],
                        "enableServiceLinks": False,
                        "priorityClassName": "system-node-critical",
                        # "terminationGracePeriodSeconds": 30,
                        "volumes": model.volumes,
                    },
                },
            },
        }

        # create deployment
        creating.create_namespaced_deployment(
            name=name, namespace=self.namespace, payload=manifest
        )

        # define service
        manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "labels": {"app": name},
                "name": name,
                "namespace": self.namespace,
            },
            "spec": {
                "ports": [{"name": "grpc", "port": 8033, "targetPort": "grpc"}],
                "selector": {"app": name},
                "type": "ClusterIP",
            },
        }

        # Change the service manifest if vllm server is to be deployed
        if type(model) is vLLMModelSpec:
            manifest["spec"]["ports"] = [
                {"name": "http", "port": 8000, "targetPort": "http"}
            ]

        # create service
        creating.create_namespaced_service(
            name=name, namespace=self.namespace, payload=manifest
        )

        out = client.CoreV1Api(self.apiclient).read_namespaced_service(
            name=name, namespace=self.namespace
        )

        if out.spec.cluster_ip is None:
            raise ValueError("ip does not exist")

        # get server url
        url = model.get_url() % (out.spec.cluster_ip)

        return DeployedModel(
            spec=model,
            name=name,
            url=url,
        )

    def delete_model(self, model: DeployedModel):
        deleting = Deleting(self.apigetter, self.logger)
        deleting.delete_namespaced_service(
            name=model.name, namespace=self.namespace, wait=False
        )
        deleting.delete_namespaced_deployment(
            name=model.name, namespace=self.namespace, wait=False
        )

    def generate_workload(
        self,
        model: Union[DeployedModel, StackSpec],
        workload: WorkloadSpec,
        filename: typing.Optional[str] = None,
        id: str = "",
    ) -> GeneratedWorkload:
        if isinstance(model, DeployedModel):
            if isinstance(model.spec, vLLMModelSpec):
                target = "vllm"
            elif isinstance(model.spec, TGISModelSpec):
                target = "tgis"
            else:
                raise TypeError("Unrecognized spec type in DeployedModel")
            model_spec = model.spec
            model_name = model.name
            model_url = model.url
        elif isinstance(model, StackSpec):
            target = "vllm"  # StackSpec always uses vLLM API
            model_spec = model
            model_name = workload.model_name if hasattr(workload, 'model_name') else model.get_available_models()[0]
            model_url = model.get_service_url()
        else:
            raise TypeError("model must be either DeployedModel or StackSpec")
        
        """Generate workload for a model deployment."""
        if isinstance(workload, GuideLLMWorkloadSpec):
            # For GuideLLMWorkloadSpec, just return the workload directly
            return GeneratedWorkload(spec=workload, file="", target=target)

        if filename is not None:
            outfile = filename
        else:
            # creating a unique ID for the workload file using hash of
            # both model spec and workload spec
            s1 = json.dumps(model_spec.__dict__, sort_keys=True)
            s2 = json.dumps(workload.__dict__, sort_keys=True)
            hash = hashlib.md5((s1 + s2).encode("utf-8")).hexdigest()
            outfile = "workload-%s.json" % (hash)

        # get volumes
        volumes, volume_mounts = self.__get_volumes_workload(model, workload)

        manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": f"fmperf-generate{'-'+id if id else ''}",
                "namespace": self.namespace,
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "fmaas-perf",
                                "image": workload.image,
                                "imagePullPolicy": "Always",
                                "env": workload.get_env(target, model, outfile),
                                "command": ["/bin/bash", "-ce"],
                                "args": workload.get_args(),
                                "volumeMounts": volume_mounts,
                                "securityContext": self.security_context,
                            }
                        ],
                        "restartPolicy": "Never",
                        "volumes": volumes,
                    }
                },
                "backoffLimit": 1,
            },
        }

        client.BatchV1Api(self.apiclient).create_namespaced_job(
            self.namespace, manifest
        )

        waiting = Waiting(self.apigetter, self.logger)
        deleting = Deleting(self.apigetter, self.logger)

        waiting.wait_for_namespaced_job(
            f"fmperf-generate{'-'+id if id else ''}", self.namespace
        )

        deleting.delete_namespaced_job(
            f"fmperf-generate{'-'+id if id else ''}", self.namespace
        )

        return GeneratedWorkload(spec=workload, file=outfile, target=target)

    def __get_volumes_workload(self, model, workload):
        if model is None:
            volumes = []
            volume_mounts = []
        elif isinstance(model, StackSpec):
            # StackSpec doesn't need volumes
            volumes = []
            volume_mounts = []
        else:
            volumes = model.spec.volumes
            volume_mounts = model.spec.volume_mounts

        if workload.pvc_name is None:
            volumes.append(
                {
                    "name": "requests",
                    "hostPath": {
                        "path": "/requests",
                    },
                }
            )
            volume_mounts.append({"mountPath": "/requests", "name": "requests"})

        else:
            # check if already mounted
            mounted_pvcs = {}
            for x in volumes:
                pvc = x.get("persistentVolumeClaim")
                if pvc is not None:
                    claim_name = pvc.get("claimName")
                    mounted_pvcs[claim_name] = x.get("name")

            if workload.pvc_name in mounted_pvcs.keys():
                volume_mounts.append(
                    {
                        "name": mounted_pvcs.get(workload.pvc_name),
                        "mountPath": "/requests",
                    }
                )
            else:
                volumes.append(
                    {
                        "name": "requests",
                        "persistentVolumeClaim": {
                            "claimName": workload.pvc_name,
                        },
                    }
                )
                volume_mounts.append(
                    {
                        "name": "requests",
                        "mountPath": "/requests",
                    }
                )

        return volumes, volume_mounts

    def evaluate(
        self,
        model: Union[DeployedModel, StackSpec],
        workload: GeneratedWorkload,
        num_users: int = 1,
        duration: str = "10s",
        backoff: str = "3s",
        grace_period: str = "10s",
        num_prom_steps: int = 30,
        prom_url: str = None,
        prom_token: str = None,
        metric_list: str = None,
        id: str = "",
    ):
        # type of service: vllm/tgis
        target = workload.target

        # get volumes
        volumes, volume_mounts = self.__get_volumes_workload(None, workload.spec)

        if isinstance(model, DeployedModel):
            model_name = model.spec.name
            model_url = model.url
        elif isinstance(model, StackSpec):
            model_name = workload.spec.model_name if hasattr(workload.spec, 'model_name') else model.get_available_models()[0]
            model_url = model.get_service_url()
        else:
            raise TypeError("model must be either DeployedModel or StackSpec")

        if isinstance(workload.spec, GuideLLMWorkloadSpec):
            # Use the environment variables from GuideLLMWorkloadSpec
            env = workload.spec.get_env(target, model, workload.file)
            job_name = f"guidellm-evaluate{'-'+id if id else ''}"
            # Add OUTPUT_PATH based on the volume mount and job name
            env.append({"name": "OUTPUT_PATH", "value": f"/requests/{job_name}"})
            
            # Add Hugging Face cache environment variables
            env.extend([
                {"name": "TRANSFORMERS_CACHE", "value": "/requests/hf_cache"},
                {"name": "HF_HOME", "value": "/requests/hf_cache"},
                {"name": "HF_DATASETS_CACHE", "value": "/requests/hf_cache/datasets"}
            ])
            
            # Add HF_TOKEN from host environment if available
            hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("hf_token") or os.environ.get("huggingface_token")
            if hf_token:
                env.append({"name": "HF_TOKEN", "value": hf_token})
                
            container_name = "guidellm-benchmark"
            container_args = []  # Use default entrypoint
        else:
            env = [
                {"name": "MODEL_ID", "value": model_name},
                {
                    "name": "URL",
                    "value": model_url,
                },
                {
                    "name": "REQUESTS_FILENAME",
                    "value": workload.file,
                },
                {
                    "name": "RESULTS_FILENAME",
                    "value": f"fmperf-results-{id}.json",
                },
                {"name": "TARGET", "value": target},
                {"name": "NUM_USERS", "value": str(num_users)},
                {"name": "DURATION", "value": duration},
                {"name": "BACKOFF", "value": backoff},
                {"name": "GRACE_PERIOD", "value": grace_period},
                {"name": "NAMESPACE", "value": self.namespace},
                {"name": "WORKLOAD_DIR", "value": "/requests"},
                {"name": "NUM_PROM_STEPS", "value": str(num_prom_steps)},
            ]

            if prom_url is not None:
                env.append({"name": "PROM_URL", "value": prom_url})

            if prom_token is not None:
                env.append({"name": "PROM_TOKEN", "value": prom_token})

            if metric_list is not None:
                env.append({"name": "TARGET_METRICS_LIST", "value": metric_list})

            job_name = f"fmperf-evaluate{'-'+id if id else ''}"
            container_name = "fmaas-perf"
            container_args = [f"python -m fmperf.loadgen.run; cat /requests/fmperf-results-{id}.json"]

        manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self.namespace,
            },
            "spec": {
                "template": {
                    "spec": {
                        "serviceAccountName": workload.spec.service_account or "vllm-router-service-account",
                        "initContainers": [
                            {
                                "name": "init-cache-dirs",
                                "image": "busybox",
                                "command": ["sh", "-c", "mkdir -p /requests/hf_cache/datasets"],
                                "volumeMounts": [
                                    {
                                        "name": "requests",
                                        "mountPath": "/requests"
                                    }
                                ]
                            }
                        ],
                        "containers": [
                            {
                                "name": container_name,
                                "imagePullPolicy": "Always",
                                "image": workload.spec.image,
                                "env": env,
                                "command": ["/bin/bash", "-ce"] if container_args else None,
                                "args": container_args,
                                "volumeMounts": volume_mounts,
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "capabilities": {
                                        "drop": ["ALL"]
                                    }
                                }
                            }
                        ],
                        "restartPolicy": "Never",
                        "volumes": volumes
                    }
                },
                "backoffLimit": 0,
            },
        }

        client.BatchV1Api(self.apiclient).create_namespaced_job(
            self.namespace, manifest
        )

        waiting = Waiting(self.apigetter, self.logger)
        deleting = Deleting(self.apigetter, self.logger)

        waiting.wait_for_namespaced_job(job_name, self.namespace)

        job_def = client.BatchV1Api(self.apiclient).read_namespaced_job(
            name=job_name, namespace=self.namespace
        )
        controllerUid = job_def.metadata.labels["controller-uid"]

        pod_label_selector = "controller-uid=" + controllerUid
        pods_list = client.CoreV1Api(self.apiclient).list_namespaced_pod(
            namespace=self.namespace,
            label_selector=pod_label_selector,
            timeout_seconds=10,
        )

        pod_name = pods_list.items[0].metadata.name

        pod_log_response = client.CoreV1Api(self.apiclient).read_namespaced_pod_log(
            name=pod_name, namespace=self.namespace
        )
        with open("pod_log_response.txt", "w") as f:
            f.write(pod_log_response)

        trimmed_response = pod_log_response.split("\n")[-1]

        try:
            out = json.loads(trimmed_response)
            perf_out, energy_out = out["results"], out["energy"]
        except Exception as e:
            print("Failed to parse logs [check pod_log_responses.txt]")
            print(e)
            perf_out, energy_out = None, None

        deleting.delete_namespaced_job(job_name, self.namespace)

        return perf_out, energy_out
