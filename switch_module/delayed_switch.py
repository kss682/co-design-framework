import math
from collections import deque
from loguru import logger
from models.stream import Packet
from models.constants import STREAM_PLACE, NETWORK_PLACE
from simpn.simulator import SimToken
from switch_module.base import Switch

class DelayedSwitch(Switch):
    name = "delayed_switch"

    def __init__(self, streams, modes, places, nodes, mode_switch, nw_function, sched, trigger_config):
        self.streams = streams
        self.hyper_cycle = self._calculate_hypercycle()
        self.delta = trigger_config["delta"]
        super().__init__(streams, modes, places, nodes, mode_switch, nw_function, sched, trigger_config)
    
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

        for mode_id, time in mode_switch:
            if time%self.hyper_cycle == 0:
                tmp = math.ceil((time+1)/self.hyper_cycle)*self.hyper_cycle
            else:
                tmp = math.ceil(time/self.hyper_cycle)*self.hyper_cycle
            switch_time.append([mode_id, tmp])
        logger.info(f"Calculating switching time: {switch_time}")
        return switch_time

    def _get_mode_period(self, mode_id):
        """Get period of the periodic stream in a mode"""
        mode = self.modes.get(mode_id)
        for st_id in mode.streams:
            stream = self.streams.get(st_id)
            if stream.triggered_by is None:
                return stream.period
        return None
    
    def _calculate_net_reconfig(self, mode_switch):
        # switch_time = deque()
        # for _id, time in mode_switch:
        #     switch_time.append([_id, time+ self.delta])
        # return switch_time
        switch_time = deque()
    
        for mode_id, time in mode_switch:
            trigger_at = self.trigger_config.get("trigger_at", 0)
            src_mode_id = self.trigger_config["mode_id"]
            p_src = self._get_mode_period(src_mode_id)
            
            app_time = time + trigger_at * p_src
            net_time = app_time + self.delta
            
            switch_time.append([mode_id, net_time])
            
            logger.info(
                f"Net switch to mode {mode_id}: "
                f"app={app_time}s, net={net_time}s, "
                f"δ={self.delta}s"
            )
        
        return switch_time
    
    def _calculate_app_switch(self, mode_switch):
        # return deque(mode_switch)
        switch_time = deque()
    
        for mode_id, time in mode_switch:
            src_mode_id = self.trigger_config["mode_id"]
            p_src = self._get_mode_period(src_mode_id)
            trigger_at = self.trigger_config.get("trigger_at", 0)
            
            app_time = time + trigger_at * p_src
            
            switch_time.append([mode_id, app_time])
            
            logger.info(
                f"App switch to mode {mode_id}: "
                f"requested={time}s, "
                f"trigger_at={trigger_at}, "
                f"actual={app_time}s"
            )
        
        return switch_time
    def _calculate_net_switch(self, mode_switch):
        return self._calculate_net_reconfig(mode_switch)