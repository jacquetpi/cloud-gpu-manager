#!/bin/bash
g5k-setup-docker
#sudo-g5k systemctl status docker

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo-g5k gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo-g5k tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo-g5k apt-get update
sudo-g5k apt-get install -y nvidia-container-toolkit
sudo-g5k nvidia-ctk runtime configure --runtime=docker
sudo-g5k systemctl restart docker

#sudo-g5k systemctl stop nvidia-persistenced
sudo-g5k systemctl stop dcgm
sudo-g5k systemctl stop dcgm-exporter
# Enable mig on g5k
gpu_count=$(nvidia-smi --format=csv,noheader  --query-gpu=count | head -n 1)
for i in $(seq 0 $(($gpu_count-1)));
do
    sudo-g5k nvidia-smi -i $i -pm 1
    sudo-g5k nvidia-smi -i $i -mig 1
    sudo-g5k nvidia-smi -i $i --gpu-reset
done
# Re-enable process
#sudo-g5k systemctl start nvidia-persistenced
sudo-g5k systemctl start dcgm
sudo-g5k systemctl start dcgm-exporter

docker build -t gpu_burn /home/pjacquet/gpu-burn