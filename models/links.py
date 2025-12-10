"""
Docstring for models.links
"""
from models.node import Node

class Link:
    """
    Docstring for Link
    """

    def __init__(self, _src: Node, _dst: Node):
        self.src = _src
        self.dst = _dst
