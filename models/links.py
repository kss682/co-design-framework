"""
Docstring for models.links
"""
from dataclasses import dataclass
from models.node import Node

@dataclass
class Link:
    src: Node
    dst: Node
