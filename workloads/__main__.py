from .workload_agent import WorkloadAgent
from .workload_burn import WorkloadBurn

if __name__ == '__main__':
    burn = WorkloadBurn()
    burn.run(gpu_id='')
    burn.wait()