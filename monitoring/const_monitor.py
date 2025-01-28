from .monitor_agent import MonitorAgent

class ConstMonitor(MonitorAgent):

    def __init__(self, labels : dict, gpu_count : int = 0, include_gpu_x : bool = False):
        self.update(labels, gpu_count, include_gpu_x)

    def discover(self):
        pass

    def query_metrics(self):
        return self.values

    def get_label(self):
        return "CONST"

    def update(self, labels : dict, gpu_count : int = 0, include_gpu_x : bool = False):
        # Apply extra labels to all domains
        domains = ['global']
        for i in range(gpu_count): domains.append('GPU' + str(i))
        if include_gpu_x: domains.append('GPU-X')
        self.values = {domain:labels for domain in domains}
