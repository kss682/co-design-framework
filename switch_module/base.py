from abc import ABC, abstractmethod
from loguru import logger
from simpn.simulator import SimToken
from models.stream import Packet
from models.constants import NETWORK_PLACE, STREAM_PLACE

class Switch(ABC):

    def __init__(self, streams, modes, places, nodes, mode_switch, nw_function, sched, trigger_config):
        self.modes = modes
        self.streams = streams
        self.places = places
        self.nodes = nodes
        self.nw_function = nw_function
        self.sched = sched
        self.trigger_config = trigger_config

        self.app_mode_switch = self._calculate_app_switch(mode_switch)
        self.net_mode_switch = self._calculate_net_switch(mode_switch)
        self.next_app_mode = self.app_mode_switch.popleft() if len(self.app_mode_switch) > 0 else None
        self.next_net_mode = self.net_mode_switch.popleft() if len(self.net_mode_switch) > 0 else None
        self.is_app_switch = False

    @abstractmethod
    def _calculate_app_switch(self, mode_switch):
        pass

    @abstractmethod
    def _calculate_net_switch(self, mode_switch):
        pass

    def _get_current_mode_id(self):
        # Read from your existing mode place
        stream_id = self.trigger_config["stream_id"]
        return self.places[STREAM_PLACE][stream_id].mode.peek().mode_id

    def check_app_switch(self, network_clock):
        """
            method checks if the application is ready to switch to next mode
        """
        # return self.next_app_mode is not None and self.next_app_mode[1] <= network_clock
        if self.next_app_mode is None:
            return False
        
        if self.next_app_mode[1] > network_clock:
            return False
        
        # Set the schedule counter for the next mode's streams to the desired start position
        next_mode_id = self.next_app_mode[0]
        next_mode = self.modes.get(next_mode_id)
        start_pos = self.trigger_config.get("next_mode", 0)
        for st_id in next_mode.streams:
            self.nw_function.set_counter(next_mode_id, st_id, start_pos)
        self.is_app_switch = True
        return True

    def check_net_switch(self, network_clock):
        """
            method checks if the network is ready to switch to next mode
        """
        if self.next_net_mode is None:
            return False

        if self.next_net_mode[1] > network_clock:
            return False
        
        if not self.is_app_switch:
            return False
        return True

    def app_switch(self, network_clock):
        logger.info(f"app reconfig triggered at {network_clock}")
        next_mode = self.modes.get(self.next_app_mode[0])

        for stream_id, stream in self.streams.items():
            if stream.triggered_by is None:
                self.places[STREAM_PLACE][stream_id].mode.marking.clear()
                self.places[STREAM_PLACE][stream_id].stream.marking.clear()
                self.places[STREAM_PLACE][stream_id].packet.marking.clear()

        for stream_id, stream in self.streams.items():
            # Only reinitialize periodic streams (those without triggered_by)
            if stream_id in next_mode.streams and stream.triggered_by is None:
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