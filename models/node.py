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


    def __repr__(self):
        return f""""Node
            (_id={self._id}, _type={self._type})
        """
