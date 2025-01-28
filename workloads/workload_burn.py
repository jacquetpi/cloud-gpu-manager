import subprocess
from .workload_agent import WorkloadAgent

class WorkloadBurn(WorkloadAgent):

    def __init__(self, container_runtime : str = 'docker', prefix : str = None):
        self.container_runtime = container_runtime
        self.prefix = prefix

    def workload(self, gpu_id : str, image : str = 'gpu_burn'):
        cmd = [self.container_runtime, 'run', '--runtime=nvidia', '-e', 'NVIDIA_VISIBLE_DEVICES=' + gpu_id, image, '-d', '120']
        if self.prefix is not None: cmd.insert(0, self.prefix)
        return cmd