#!/bin/bash
g5k-setup-docker -t

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo-g5k gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo-g5k tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo-g5k apt-get update
sudo-g5k apt-get install -y nvidia-container-toolkit
sudo-g5k nvidia-ctk runtime configure --runtime=docker
sudo-g5k systemctl restart docker

curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube_latest_amd64.deb
sudo-g5k dpkg -i minikube_latest_amd64.deb

curl -LO https://github.com/Mirantis/cri-dockerd/releases/download/v0.3.16/cri-dockerd_0.3.16.3-0.debian-bullseye_amd64.deb
sudo-g5k dpkg -i cri-dockerd_0.3.16.3-0.debian-bullseye_amd64.deb

# Dangerous life
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

minikube start
minikube kubectl -- get po -A

helm install --wait --generate-name -n gpu-operator --create-namespace nvidia/gpu-operator

minikube kubectl -- create -n gpu-operator -f time-slicing-config.yaml
minikube kubectl -- patch clusterpolicies.nvidia.com/cluster-policy \
    -n gpu-operator --type merge \
    -p '{"spec": {"devicePlugin": {"config": {"name": "time-slicing-config-all", "default": "any"}}}}'

minikube kubectl -- describe nodes
minikube kubectl create deployment hello-minikube --image=kicbase/echo-server:1.0

cat <<EOF | minikube kubectl -- apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
spec:
  restartPolicy: Never
  containers:
  - name: cuda-container
    image: nvidia/cuda:11.8.0-runtime-ubuntu22.04
    command: ["nvidia-smi"]
    resources:
      limits:
        nvidia.com/gpu: 1
EOF

eval $(minikube docker-env)
docker build -t gpu_burn /home/pjacquet/gpu-burn
minikube image load gpu_burn
cat <<EOF | minikube kubectl -- apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-burn
spec:
  restartPolicy: Never
  containers:
  - name: container-burn
    image: gpu_burn
    imagePullPolicy: Never
    command: ["./gpu_burn","-d","120"]
    resources:
      limits:
        nvidia.com/gpu: 1
EOF