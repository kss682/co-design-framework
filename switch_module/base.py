from abc import ABC, abstractmethod
from loguru import logger
from simpn.simulator import SimToken
from models.stream import Packet
from models.constants import NETWORK_PLACE, STREAM_PLACE

class Switch(ABC):
    """
    Docstring for Base switch class
    """

    def __init__(self, streams, modes, places, nodes, mode_switch):
        self.modes = modes
        self.streams = streams
        self.places = places
        self.nodes = nodes
        self.app_mode_switch = self._calculate_app_switch(mode_switch)
        self.net_mode_switch = self._calculate_net_switch(mode_switch)
        self.next_app_mode = self.app_mode_switch.popleft() if len(self.app_mode_switch) > 0 else None
        self.next_net_mode = self.net_mode_switch.popleft() if len(self.net_mode_switch) > 0 else None

    @abstractmethod
    def _calculate_app_switch(self, mode_switch):
        pass

    @abstractmethod
    def _calculate_net_switch(self, mode_switch):
        pass

    def check_app_switch(self, network_clock):
        """
            method checks if the application is ready to switch to next mode
        """
        return self.next_app_mode is not None and self.next_app_mode[1] <= network_clock

    def check_net_switch(self, network_clock):
        """
            method checks if the network is ready to switch to next mode
        """
        return self.next_net_mode is not None and self.next_net_mode[1] <= network_clock

    def app_switch(self, network_clock):
        """
        Docstring for switch
        
        :param self: Description
        :param network_clock: Description
        """
        logger.info(f"app reconfig triggered at {network_clock}")
        next_mode = self.modes.get(self.next_app_mode[0])

        for stream_id, stream in self.streams.items():
            if stream.triggered_by is None:
                self.places[STREAM_PLACE][stream_id].mode.marking.clear()
                self.places[STREAM_PLACE][stream_id].stream.marking.clear()
                self.places[STREAM_PLACE][stream_id].packet.marking.clear()

        for stream_id, stream in self.streams.items():
            if stream_id in next_mode.streams:
                self.places[STREAM_PLACE][stream_id].mode.add_token(SimToken(next_mode, time=network_clock))
                self.places[STREAM_PLACE][stream_id].packet.add_token(
                    SimToken(
                        Packet(
                            seq_id=1,
                            stream_id=stream.stream_id,
                            packet_time=0,
                            mode_seq=str(next_mode.mode_id)+"@"+str(network_clock)
                        ), 
                        time=network_clock
                        )
                )
                self.places[STREAM_PLACE][stream_id].stream.add_token(SimToken(stream, time=network_clock))


        self.next_app_mode = self.app_mode_switch.popleft() if len(self.app_mode_switch) > 0 else None

    def net_switch(self, network_clock):
        next_mode = self.modes.get(self.next_net_mode[0])

        logger.info(f"network reconfig triggered at {network_clock}")
        for node_id, node in self.nodes.items():
            if node.node_type == "NN":
                self.places[NETWORK_PLACE][node_id].mode.marking.clear()
                self.places[NETWORK_PLACE][node_id].mode.add_token(SimToken(next_mode, time=network_clock))

        self.next_net_mode = self.net_mode_switch.popleft() if len(self.net_mode_switch) > 0 else None