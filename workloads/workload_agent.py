import subprocess as sp

class WorkloadAgent:

    def __init__(self, name: str):
        self.name = name
        self.process = None

    def run(self, **args):
        self.process = sp.Popen(self.workload(**args))

    def wait(self):
        if self.process is not None:
            self.process.communicate()

    def workload(self):
        """Launch the workload"""
        raise NotImplementedError("This method should be implemented in subclasses.")