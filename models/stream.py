""""
    Docs
"""
from dataclasses import dataclass
from models.node import Node

@dataclass
class Stream:
    """
    Docstring for Message
    """
    _id: int
    src: Node
    dst: Node
    traffic_type:str
    release_time: int
    period: int
    deadline: int
    # birthtime: int

    # def reset_birthtime(self):
        # self.birthtime += self.period

@dataclass
class Packet:
    stream_id: int
    seq_id: int
    packet_time: int
    mode_seq: str

@dataclass
class Timer:
    seq_id: int