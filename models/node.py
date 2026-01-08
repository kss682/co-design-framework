"""
Docstring for models.node
"""
from enum import Enum
from collections import defaultdict
class NodeTypes(Enum):
    ES = "end_system"
    NN = "network_node"

class Node:
    """
    Class Node represents nodes in the network and
    their properties. They nodes are modelled as 
    """

    def __init__(self, _id: int, _type: str):
        self._id = _id
        self._type = _type
        self.last_packet_seen = defaultdict(dict)
