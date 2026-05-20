from dataclasses import dataclass
from models.node import Node
from typing import Optional
from simpn.simulator import SimVar




@dataclass
class Stream:
    stream_id: int
    src: Node
    dst: Node
    traffic_type:str
    release_time: Optional[int]
    period: Optional[int]
    deadline: Optional[int]
    triggered_by: Optional[int]
    plant_id: Optional[int] = None

@dataclass
class Packet:
    stream_id: int
    seq_id: int
    packet_time: int
    mode_seq: str

@dataclass
class Timer:
    seq_id: int