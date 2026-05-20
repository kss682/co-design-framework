import math
from collections import deque
from loguru import logger
from models.constants import STREAM_PLACE, NETWORK_PLACE
from models.stream import Packet
from simpn.simulator import SimToken
from switch_module.base import Switch

class SynchSwitch(Switch):
    """
    Docstring for SynchSwitch
        - implments the logic for synced switching by 
        considering the hypercycle of all streams in the model
    This is based on the assumption that all the schedules are ready to be configured within a hypercycle
    """
    name = "hypercycle_switch"
    def __init__(self, streams, modes, places, nodes, mode_switch):
        self.streams = streams
        self.hyper_cycle = self._calculate_hypercycle()
        super().__init__(streams, modes, places, nodes, mode_switch)
        

    def _calculate_hypercycle(self):
        periods = [int(v.period*1000) for key, v in self.streams.items() if v.triggered_by is None]
        return math.lcm(*periods)/1000
    
    def _calculate_switchingtime(self, mode_switch):
        switch_time = deque()

        for mode_id, time in mode_switch:
            if time%self.hyper_cycle == 0:
                tmp = math.ceil((time+1)/self.hyper_cycle)*self.hyper_cycle
            else:
                tmp = math.ceil(time/self.hyper_cycle)*self.hyper_cycle
            switch_time.append([mode_id, tmp])
        logger.info(f"Calculating switching time: {switch_time}")
        return switch_time
    
    def _calculate_app_switch(self, mode_switch):
        return self._calculate_switchingtime(mode_switch)
    
    def _calculate_net_switch(self, mode_switch):
        return self._calculate_switchingtime(mode_switch)