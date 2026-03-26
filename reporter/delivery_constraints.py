from dataclasses import dataclass

@dataclass
class PacketDeliveryConstraints:
    mode_id: int
    stream_id: int
    min_packets: int
    window_size: int

@dataclass
class Guarantee:
    window_violation: bool
    deadline_miss_rate: float
    max_interrupt_time: float
    control_violation: bool