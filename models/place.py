from typing import Optional
from dataclasses import dataclass
from simpn.simulator import SimVar

@dataclass
class NetworkPlace:
    """Represents network related places on the Petri net."""
    node: Optional[SimVar] = None
    mode: Optional[SimVar] = None

@dataclass
class StreamPlace:
    """Represents stream related places on the Petri net."""
    mode: Optional[SimVar] = None
    packet: Optional[SimVar] = None
    stream: Optional[SimVar] = None
    triggered_by: Optional[SimVar] = None
    done: Optional[SimVar] = None