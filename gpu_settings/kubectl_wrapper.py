import subprocess
import re

class KubectlWrapper(object):
    def __init__(self, prefix_command: list = ['minikube', 'kubectl', '--']):
        self.prefix_command = prefix_command

    def set_kube_replicas_policy(self, replicas: int, namespace: str = "gpu-operator", config_name: str = "oversub-all"):
        config_yaml = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {config_name}
data:
  any: |-
    version: v1
    flags:
      migStrategy: none
    sharing:
      timeSlicing:
        resources:
        - name: nvidia.com/gpu
          replicas: {replicas}
"""
        process = subprocess.run(
            self.prefix_command + ["apply", "-n", namespace, "-f", "-"],
            input=config_yaml,
            text=True,
            capture_output=True
        )

        if process.returncode == 0:
            print("ConfigMap updated successfully.")
        else:
            print("Error updating ConfigMap:", process.stderr)

    def patch_cluster_policy(self, namespace: str = "gpu-operator", policy_name: str = "cluster-policy", config_name: str = "oversub-all-2", default_value: str = "any"):
        patch_data = f'{{"spec": {{"devicePlugin": {{"config": {{"name": "{config_name}", "default": "{default_value}"}}}}}}}}'
        process = subprocess.run(
            self.prefix_command + ["patch", f"clusterpolicies.nvidia.com/{policy_name}", "-n", namespace, "--type", "merge", "-p", patch_data],
            text=True,
            capture_output=True
        )

        if process.returncode == 0:
            print("Cluster policy patched successfully.")
        else:
            print("Error patching cluster policy:", process.stderr)

    def get_current_oversub_policy(self):
        process = subprocess.run(
            self.prefix_command + ["describe", "nodes"],
            text=True,
            capture_output=True
        )
        if process.returncode != 0:
            print("Error retrieving node description:", process.stderr)
            return None

        match = re.search(r"nvidia.com/gpu\.replicas=(\d+)", process.stdout)
        if match:
            return int(match.group(1))

        print("No replicas information found.")
        return None

    def get_gpu_instance_count(self):
        process = subprocess.run(
            self.prefix_command + ["describe", "nodes"],
            text=True,
            capture_output=True
        )
        if process.returncode != 0:
            print("Error retrieving node description:", process.stderr)
            return None

        match = re.search(r"nvidia.com/gpu:\s+(\d+)", process.stdout)
        if match:
            return int(match.group(1))

        print("No GPU instance information found.")
        return None

    def launch_pods(self, num_pods: int, image: str = "gpu_burn", command: list = ["./gpu_burn", "-d", "3600"], namespace: str = "default"):
        pod_yaml = ""
        for i in range(num_pods):
            pod_name = f"gpu-burn-{i}"
            # Delete the pod if it already exists
            subprocess.run(
                self.prefix_command + ["delete", "pod", pod_name, "-n", namespace, "--ignore-not-found"],
                text=True,
                capture_output=True
            )

        pod_yaml += f"""---
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
spec:
  restartPolicy: Never
  containers:
  - name: container-burn
    image: {image}
    imagePullPolicy: Never
    command: {command}
    resources:
      limits:
        nvidia.com/gpu: 1
"""
        # Apply the updated YAML to create new pods
        process = subprocess.run(
            self.prefix_command + ["apply", "-n", namespace, "-f", "-"],
            input=pod_yaml,
            text=True,
            capture_output=True
        )
        if process.returncode == 0:
            print(f"{num_pods} pods launched successfully.")
        else:
            print("Error launching pods:", process.stderr)

    def destroy_all_pods(self, namespace: str = "default"):
        process = subprocess.run(
            self.prefix_command + ["delete", "pods", "--all", "-n", namespace],
            text=True,
            capture_output=True
        )

        if process.returncode == 0:
            print("All pods deleted successfully.")
        else:
            print("Error deleting pods:", process.stderr)
