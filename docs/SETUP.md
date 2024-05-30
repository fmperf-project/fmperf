# Setting up a local k8s cluster

Below, we provide instructions for creating a single-node, local kubernetes (k8s) cluster on a development machine **without** super-user permissions and **with** GPU support.

## Install kubectl

```shell
curl -LO https://dl.k8s.io/release/v1.24.12/bin/linux/amd64/kubectl
chmod +x kubectl
mkdir -p ~/bin
mv kubectl ~/bin/
```

Make sure that the `~/bin` directory is prepended to your `PATH` environment variable.

Verify the instllation:
```shell
$ which kubectl
~/bin/kubectl
$ kubectl version
WARNING: This version information is deprecated and will be replaced with the output from kubectl version --short.  Use --output=yaml|json to get the full version.
Client Version: version.Info{Major:"1", Minor:"24", GitVersion:"v1.24.12", GitCommit:"ef70d260f3d036fc22b30538576bbf6b36329995", GitTreeState:"clean", BuildDate:"2023-03-15T13:37:18Z", GoVersion:"go1.19.7", Compiler:"gc", Platform:"linux/amd64"}
Kustomize Version: v4.5.4
The connection to the server localhost:8080 was refused - did you specify the right host or port?
```

## Install helm

```shell
wget https://get.helm.sh/helm-v3.11.3-linux-amd64.tar.gz
tar -xvzf helm-v3.11.3-linux-amd64.tar.gz
mv linux-amd64/helm ~/bin/
```

Verify installation:
```shell
$ which helm
~/bin/helm
$ helm version
version.BuildInfo{Version:"v3.11.3", GitCommit:"323249351482b3bbfc9f5004f65d400aa70f9ae7", GitTreeState:"clean", GoVersion:"go1.20.3"}
```

## Compile and install Kind

We can use `kind` to deploy a single-node k8s cluster on any development machine.
Kind is preferable to others solutions like microk8s because it does not require sudo permissions.
It does however require that the user be able to run docker containers (e.g., that the user is added to the docker group).
Kind does not have GPU support, but there exists a [forked version](https://jacobtomlinson.dev/posts/2022/quick-hack-adding-gpu-support-to-kind/) (with minimal diff) enabling this.
We start by compiling kind with GPU support from source:
```shell
git clone -b gpu https://github.com/jacobtomlinson/kind
cd kind
make build
mv bin/kind ~/bin/
```

And verify the installation:
```shell
$ which kind
~/bin/kind
$ kind version
kind (@jacobtomlinson's patched GPU edition) v0.18.0-alpha.702+ec8f4c936a5171 go1.19.3 linux/amd64
```

## Create k8s cluster

Now let's use kind to create a local k8s cluster.

Firstly, create a file called `kind-gpu.yaml` with the following contents:
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: gpu-test
nodes:
  - role: control-plane
    image: kindest/node:v1.24.12@sha256:1e12918b8bc3d4253bc08f640a231bb0d3b2c5a9b28aa3f2ca1aee93e1e8db16
    gpus: true
    extraMounts:
      - hostPath: /localhome/models
        containerPath: /models
      - hostPath: /localhome/requests
        containerPath: /requests
```
In the above `/localhome/models` and `/localhome/requests` are two directories that we will use to persist model weights and generated requests respectively.
Please ensure that these directories (or their equivalent) exist and are both read and writeable by other users.

Then execute the following which create the cluster:
```shell
$ kind create cluster --config kind-gpu.yaml
Creating cluster "gpu-test" ...
 ✓ Ensuring node image (kindest/node:v1.24.12) 🖼
 ✓ Preparing nodes 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
Set kubectl context to "kind-gpu-test"
You can now use your cluster with:

kubectl cluster-info --context kind-gpu-test

Have a question, bug, or feature request? Let us know! https://kind.sigs.k8s.io/#community 🙂
```

Let's verify the status of the clusters with:
```shell
$ kubectl cluster-info --context kind-gpu-test
Kubernetes control plane is running at https://127.0.0.1:42303
CoreDNS is running at https://127.0.0.1:42303/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.
```
```shell
$ kubectl get nodes
NAME                     STATUS   ROLES           AGE   VERSION
gpu-test-control-plane   Ready    control-plane   77s   v1.24.12
```
```shell
$ kubectl get pods -A
NAMESPACE            NAME                                             READY   STATUS    RESTARTS   AGE
kube-system          coredns-57575c5f89-djgdt                         1/1     Running   0          50s
kube-system          coredns-57575c5f89-kktz8                         1/1     Running   0          50s
kube-system          etcd-gpu-test-control-plane                      1/1     Running   0          66s
kube-system          kindnet-tdrcj                                    1/1     Running   0          51s
kube-system          kube-apiserver-gpu-test-control-plane            1/1     Running   0          64s
kube-system          kube-controller-manager-gpu-test-control-plane   1/1     Running   0          64s
kube-system          kube-proxy-dd6r4                                 1/1     Running   0          51s
kube-system          kube-scheduler-gpu-test-control-plane            1/1     Running   0          64s
local-path-storage   local-path-provisioner-6dfffb7d87-czcv2          1/1     Running   0          50s
```

## Install NVIDIA GPU Operator

In order for the pods to be able to access the GPUs of the machine, we now need to install the NVIDIA GPU Operator into the cluster:

```shell
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm repo update
helm install nvidia/gpu-operator \
  --wait --generate-name \
  --create-namespace -n gpu-operator \
  --set driver.enabled=false \
  --set mig.strategy=none \
  --version 23.3.1
```

It takes a while until the associated pods are all up-and-running.
When everything is ready, the pods in the `gpu-operator` namespace should look like:
```shell
$ kubectl get pods -n gpu-operator
NAME                                                              READY   STATUS      RESTARTS   AGE
gpu-feature-discovery-wqxt2                                       1/1     Running     0          114s
gpu-operator-1682586521-node-feature-discovery-master-764fc4245   1/1     Running     0          2m18s
gpu-operator-1682586521-node-feature-discovery-worker-g9rwp       1/1     Running     0          2m18s
gpu-operator-7cbb496c4c-bm2s4                                     1/1     Running     0          2m18s
nvidia-container-toolkit-daemonset-fvvm6                          1/1     Running     0          114s
nvidia-cuda-validator-db6bx                                       0/1     Completed   0          72s
nvidia-dcgm-exporter-fj8ct                                        1/1     Running     0          114s
nvidia-device-plugin-daemonset-xjb5f                              1/1     Running     0          114s
nvidia-device-plugin-validator-dm69w                              0/1     Completed   0          14s
nvidia-operator-validator-ztpls                                   1/1     Running     0          114s
```
## Loading a local fmperf image into the cluster node

Currently the fmperf load-tesing docker image is not available on a remote registry. Therefore,  we need to build a docker image from the Dockerfile provided in the repo, and load it into the cluster node.

```
docker build -t fmperf-project/fmperf:local .
kind load fmperf-project/fmperf:local --name gpu-test
```

You can verify if this image is correctly loaded into the cluster node:

```
docker exec -it gpu-test-control-plane crictl images | grep local

docker.io/fmperf-project/fmperf   local   c20f63b5bb19d    992M
```

The cluster is now ready to run the benchmark. As a first try, run the examples/example_vllm.py script.
