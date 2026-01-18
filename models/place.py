from typing import Optional
from dataclasses import dataclass
from simpn.simulator import SimVar

@dataclass
class NetworkPlace:
    """
    Docstring
    Represents network related places on the petri net
    """
    node: Optional[SimVar] = None
    mode: Optional[SimVar] = None

@dataclass
class StreamPlace:
    """
    Docstring for StreamPlace class (used to represent stream related places on the petri net)
    """
    mode: Optional[SimVar] = None
    packet: Optional[SimVar] = None
    stream: Optional[SimVar] = None
    triggered_by: Optional[SimVar] = None
    done: Optional[SimVar] = None