import math
from collections import deque
from loguru import logger
from models.stream import Packet
from simpn.simulator import SimToken

class SynchSwitch:
    """
    Docstring for SynchSwitch
        - implments the logic for synced switching by 
        considering the hypercycle of all streams in the model
    This is based on the assumption that all the schedules are ready to be configured within a hypercycle
    """
    name = "hypercycle_switch"
    def __init__(self, streams, modes, places, nodes, mode_switch):
        self.modes = modes
        self.streams = streams
        self.places = places
        self.nodes = nodes
        self.hyper_cycle = self._calculate_hypercycle()
        self.app_mode_switch = self._calculate_switchingtime(mode_switch)
        self.net_mode_switch = self._calculate_switchingtime(mode_switch)
        self.next_app_mode = self.app_mode_switch.popleft() if len(self.app_mode_switch) > 0 else None
        self.next_net_mode = self.net_mode_switch.popleft() if len(self.net_mode_switch) > 0 else None

    def _calculate_hypercycle(self):
        periods = [int(v.period*1000) for key, v in self.streams.items() if v.triggered_by is None]
        return math.lcm(*periods)/1000
    
    def _calculate_switchingtime(self, mode_switch):
        """
        Docstring for _calculate_switchingtime
        
        :param self: Description
        :param mode_switch: Description [(mode_id, switch_time)] 
                            switch time represents application time at which application requests switch
        """
        switch_time = deque()

        for id, time in mode_switch:
            if time%self.hyper_cycle == 0:
                tmp = math.ceil((time+1)/self.hyper_cycle)*self.hyper_cycle
            else:
                tmp = math.ceil(time/self.hyper_cycle)*self.hyper_cycle
            switch_time.append([id, tmp])
        logger.info(f"Calculating switching time: {switch_time}")
        return switch_time

    def check_app_switch(self, network_clock):
        return self.next_app_mode is not None and self.next_app_mode[1] <= network_clock

    def check_net_switch(self, network_clock):
        return self.next_net_mode is not None and self.next_net_mode[1] <= network_clock
    
    def app_switch(self, network_clock):
        """
        Docstring for switch
        
        :param self: Description
        :param network_clock: Description
        """
        next_mode = self.modes.get(self.next_app_mode[0])

        for _id, stream in self.streams.items():
            self.places[stream.src._id]["mode"].marking.clear()
            self.places[stream.src._id]["stream"].marking.clear()
            self.places[stream.src._id]["packet"].marking.clear()
            # import pdb
            # breakpoint()
        
        for _id, stream in self.streams.items():
            if _id in next_mode.streams:
                self.places[stream.src._id]["mode"].add_token(SimToken(next_mode, time=network_clock))
                self.places[stream.src._id]["packet"].add_token(
                       SimToken(Packet(
                            seq_id=1,
                            stream_id=stream._id,
                            packet_time=0,
                            mode_seq=str(next_mode._id)+"@"+str(network_clock)
                        ),
                            time=network_clock
                        )
                    )
                self.places[stream.src._id]["stream"].add_token(SimToken(stream, time=network_clock))

        self.next_app_mode = self.app_mode_switch.popleft() if len(self.app_mode_switch) > 0 else None


    def net_switch(self, network_clock):
        next_mode = self.modes.get(self.next_net_mode[0])

        logger.info(f"network reconfig triggered at {network_clock}")
        for _id, node in self.nodes.items():
            if node._type == "NN":
                self.places[_id]["mode"].marking.clear()
                self.places[_id]["mode"].add_token(SimToken(next_mode, time=network_clock))
                self.places[_id]["packet_last_seen"].clear()

        self.next_net_mode = self.net_mode_switch.popleft() if len(self.net_mode_switch) > 0 else None