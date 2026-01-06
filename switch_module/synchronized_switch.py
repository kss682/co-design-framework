import math
import logging
from collections import deque

from models.stream import Packet
from simpn.simulator import SimToken

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class SynchSwitch:
    """
    Docstring for SynchSwitch
        - implments the logic for synced switching by 
        considering the hypercycle of all streams in the model
    This is based on the assumption that all the schedules are ready to be configured within a hypercycle
    """
    def __init__(self, streams, modes, places, nodes, mode_switch):
        self.modes = modes
        self.streams = streams
        self.places = places
        self.nodes = nodes
        self.hyper_cycle = self._calculate_hypercycle()
        self.mode_switch = self._calculate_switchingtime(mode_switch)
        self.next_mode = self.mode_switch.popleft() if len(self.mode_switch) > 0 else None

    def _calculate_hypercycle(self):
        periods = [v.period for key, v in self.streams.items()]
        return math.lcm(*periods)
    
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

    def check_switch(self, network_clock):
        return self.next_mode is not None and self.next_mode[1] <= network_clock

    
    def switch(self, network_clock):
        """
        Docstring for switch
        
        :param self: Description
        :param network_clock: Description
        """
        next_mode = self.modes.get(self.next_mode[0])

        for _id, stream in self.streams.items():
            self.places[stream.src._id]["mode"].marking.clear()
            self.places[stream.src._id]["stream"].marking.clear()
            self.places[stream.src._id]["packet"].marking.clear()

            if _id in next_mode.streams:
                self.places[stream.src._id]["mode"].add_token(SimToken(next_mode, time=network_clock))
                self.places[stream.src._id]["packet"].add_token(
                       SimToken(Packet(
                            seq_id=1,
                            stream_id=stream._id
                        ),
                            time=network_clock
                        )
                    )
                self.places[stream.src._id]["stream"].add_token(SimToken(stream, time=network_clock))
       
        logger.info("network reconfig triggered at %s", network_clock)
        for _id, node in self.nodes.items():
            if node._type == "NN":
                self.places[_id]["mode"].marking.clear()
                self.places[_id]["mode"].add_token(SimToken(next_mode, time=network_clock))
        net_switch = False

        self.next_mode = self.mode_switch.popleft() if len(self.mode_switch) > 0 else None
