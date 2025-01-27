from .monitor_agent import MonitorAgent

class ConstMonitor(MonitorAgent):

    def __init__(self, values : dict):
        self.values = values

    def discover(self):
        pass

    def query_metrics(self):
        return self.values

    def get_label(self):
        return "CONST"


    def update(self, args):
        self.values = args