class WorkloadAgent:

    def __init__(self, name: str):
        self.name = name

    def workload(self):
        """Launch the workload"""
        raise NotImplementedError("This method should be implemented in subclasses.")