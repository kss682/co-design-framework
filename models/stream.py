""""
    Docs
"""
from dataclasses import dataclass
from models.node import Node
from typing import Optional
from simpn.simulator import SimVar




@dataclass
class Stream:
    """
    Docstring for Message
    """
    stream_id: int
    src: Node
    dst: Node
    traffic_type:str
    release_time: Optional[int]
    period: Optional[int]
    deadline: Optional[int]
    triggered_by: Optional[int]

@dataclass
class Packet:
    """"
    Docstring for Packet
    """
    stream_id: int
    seq_id: int
    packet_time: int
    mode_seq: str

@dataclass
class Timer:
    """
    Docstring for Timer
    """
    seq_id: int