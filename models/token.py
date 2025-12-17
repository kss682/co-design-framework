from simpn.simulator import SimVar, SimToken


class SimVarMonitor(SimVar):

    def __init__(self, name, release_time, network):
        super().__init__(name)
        self.release_time = release_time
        self.log = []
        self.network = network
    
    def put(self, token):
        super.put(token)

        print(self.network.clock)
    
    def add_token(self, token, count=1):
        super().add_token(token, count)
        print(self.network.clock)