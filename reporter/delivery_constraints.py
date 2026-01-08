from dataclasses import dataclass

@dataclass
class PacketDeliveryConstraints:
    mode_id: int
    stream_id: int
    min_packets: int
    window_size: int