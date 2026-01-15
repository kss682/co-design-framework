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

    def __init__(self, node_id: int, node_type: str):
        self.node_id = node_id
        self.node_type = node_type
        self.last_packet_seen = defaultdict(dict)


    def __repr__(self):
        return f""""Node
            (_id={self.node_id}, _type={self.node_type})
        """
