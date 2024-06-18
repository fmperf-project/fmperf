# Setting up a local k8s cluster

Below, we provide instructions for creating a single-node, local kubernetes (k8s) cluster on a development machine **with** GPU support.

## Prerequisites
1. NVIDIA container toolkit is installed on the node.
2. The default runtime runtime for Docker is set to NVIDIA:
```
sudo nvidia-ctk runtime configure --runtime=docker --set-as-default
sudo systemctl restart docker
```
3. Configure the NVIDIA Container Runtime to use volume mounts to select devices to inject into a container.
```
sudo nvidia-ctk config --set accept-nvidia-visible-devices-as-volume-mounts=true --in-place
```

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

## Install kind

```shell
# Based on https://kind.sigs.k8s.io/docs/user/quick-start#installing-from-release-binaries
# For AMD64 / x86_64
[ $(uname -m) = x86_64 ] && curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64
# For ARM64
[ $(uname -m) = aarch64 ] && curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-arm64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

And verify the installation:
```shell
$ which kind
/usr/local/bin/kind
$ kind version
kind v0.23.0 go1.21.10 linux/amd64
```

## Create k8s cluster

Now let's use kind to create a local k8s cluster.

Firstly, create a file called `kind-gpu.yaml` with the following contents:
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: fmperf-cluster
nodes:
  - role: control-plane
    extraMounts:
      - hostPath: /dev/null
        containerPath: /var/run/nvidia-container-devices/all
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
Creating cluster "fmperf-cluster" ...
 ✓ Ensuring node image (kindest/node:v1.30.0) 🖼
 ✓ Preparing nodes 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
Set kubectl context to "kind-fmperf-cluster"
You can now use your cluster with:

kubectl cluster-info --context kind-fmperf-cluster

Have a question, bug, or feature request? Let us know! https://kind.sigs.k8s.io/#community 🙂
```

Let's verify the status of the clusters with:
```shell
$ kubectl cluster-info --context kind-fmperf-cluster

Kubernetes control plane is running at https://127.0.0.1:36111
CoreDNS is running at https://127.0.0.1:36111/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.
```
```shell
$ kubectl get nodes
NAME                           STATUS   ROLES           AGE     VERSION\
fmperf-cluster-control-plane   Ready    control-plane   8m22s   v1.30.0
```
```shell
$ kubectl get pods -A
NAMESPACE            NAME                                                   READY   STATUS    RESTARTS   AGE
kube-system          coredns-7db6d8ff4d-hnlnw                               1/1     Running   0          8m30s
kube-system          coredns-7db6d8ff4d-mxmpw                               1/1     Running   0          8m30s
kube-system          etcd-fmperf-cluster-control-plane                      1/1     Running   0          8m45s
kube-system          kindnet-sw8f9                                          1/1     Running   0          8m30s
kube-system          kube-apiserver-fmperf-cluster-control-plane            1/1     Running   0          8m45s
kube-system          kube-controller-manager-fmperf-cluster-control-plane   1/1     Running   0          8m45s
kube-system          kube-proxy-5mb4x                                       1/1     Running   0          8m30s
kube-system          kube-scheduler-fmperf-cluster-control-plane            1/1     Running   0          8m44s
local-path-storage   local-path-provisioner-988d74bc-74ztt                  1/1     Running   0          8m30s
```

## Install NVIDIA GPU Operator

In order for the pods to be able to access the GPUs of the machine, we now need to install the NVIDIA GPU Operator into the cluster:

```shell
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm repo update
helm install nvidia/gpu-operator \
  --wait --generate-name \
  --create-namespace -n gpu-operator \
  --set driver.enabled=false
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

The cluster is now ready to run the benchmark. As a first try, run the examples/example_vllm.py script.

## Troubleshooting
1. If you see `/proc/driver/nvidia/capabilities: no such file or directory: unknown`
Consider uninstalling the NVIDIA GPU operator, run `docker exec -it fmperf-cluster-control-plane umount -R /proc/driver/nvidia`, and then re-install the Nvidia GPU operator.
