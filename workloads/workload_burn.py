import subprocess
from .workload_agent import WorkloadAgent

class WorkloadBurn(WorkloadAgent):

    def __init__(self):
        pass

    def workload(cls, mig_identifier : str, image : str = 'gpu_burn'):
        cmd_dci = ["docker", 'run', '--runtime=nvidia', '-e', 'NVIDIA_VISIBLE_DEVICES=' + mig_identifier, image, 'nvidia-smi', '-L']
        subprocess.call(cmd_dci)