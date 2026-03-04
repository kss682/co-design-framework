import argparse
import math
import json
import random
from collections import defaultdict
from collections import deque
from loguru import logger

from models.node import Node
from models.links import Link
from models.stream import Stream, Packet, Timer
from models.place import StreamPlace, NetworkPlace
from models.constants import STREAM_PLACE, NETWORK_PLACE
from models.mode import Mode
from switch_module.synchronized_switch import SynchSwitch
from switch_module.delayed_switch import DelayedSwitch

from reporter.time_reporter import TimesReporter
from reporter.delivery_constraints import Guarantee, PacketDeliveryConstraints
from simpn.simulator import SimProblem, SimToken
from simpn.visualisation import Visualisation

import sys
sys.setrecursionlimit(10000)


# SWITCH_STRATEGY = [
#     # SynchSwitch
#     DelayedSwitch
# ]


def load_data(filename:str):
    """
    Docstring for load_data
    
    :param filename: name of file to load data
    :return: data 
    :rtype: dict | None
    """
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        logger.info("network model loaded from %s", filename)    
        return data
    except Exception as e:
        logger.error("failed to load network model from %s due to %s", filename, e)
        return None

## Modularize this function to make it testable
def load_network(data: dict):
    """
    Docstring for load_network
    
    :param data: Description
    :type data: dict
    """
    nodes:dict = {}
    links:list = []
    streams:dict = {}
    modes:dict = {}

    # Need to extract this out into a validation function that does strict checking on the json
    if data.get('nodes', None) is None or data.get('links', None) is None or data.get('streams', None) is None:        
        logger.info("missing information in json, please validate")
        close_pgm()

    for node in data.get("nodes"):
        nodes[node.get("id")] = Node(
                node_id=node.get('id'),
                node_type=node.get('type')
            )

    logger.info(f"{len(nodes)} nodes found in the network", len(nodes))

    for lnk in data.get('links'):
        links.append(
            Link(
                src=nodes.get(lnk.get("src")),
                dst=nodes.get(lnk.get("dst"))
            )
        )

    logger.info(f"{len(links)} links found in the network")

    for stm in data.get('streams'):
        streams[stm.get("id")] = Stream(
                stream_id=stm.get("id"),
                src=nodes.get(stm.get("src")),
                dst=nodes.get(stm.get("dst")),
                traffic_type=stm.get("type"),
                release_time=stm.get("release_time", None),
                period=stm.get("period", None),
                deadline=stm.get("deadline", None),
                triggered_by=stm.get("triggered_by", None),
                plant_id=stm.get("plant_id", None)
            )
    logger.info(f" {len(streams)} streams found in the network")

    for mode_id in data.get("modes").keys():
        mode = data.get("modes")[mode_id]
        logger.info("%s", mode)
        modes[int(mode_id)] = Mode(
             mode_id=int(mode_id),
             name=mode.get("name"),
             streams=mode.get("streams"),
             schedule=mode.get("schedule_id")
            )
    logger.info(f"{len(modes)} modes found in the network", len(modes))

    schedules = data.get("schedules")
    mode_switch = data.get("mode_switch")

    link_delays = data.get("link_delay", {})
    pre_condition_rate = data.get("preconditions", {}).get("network_nodes")

    delivery_constraints = {}
    for constranint in data.get("delivery_constraints", []):
        delivery_constraints[(constranint.get("mode_id"), constranint.get("stream_id"))] = PacketDeliveryConstraints(**constranint)

    return (nodes,
            links,
            streams,
            modes,
            schedules,
            deque(mode_switch),
            link_delays,
            pre_condition_rate,
            delivery_constraints
    )


def close_pgm():
    """
    Docstring for close_pgm
    
    :return: Description
    :rtype: NoReturn
    """
    logger.info("closing simulation due to error")
    exit(1)


def generate_packet_function(mode_dict):
    """
    """
    def timer_function(mode, packet, stream):

        if mode_dict.get(mode.mode_id, None) is not None and stream.stream_id in mode_dict.get(mode.mode_id).streams:
            return [        
                SimToken(mode, delay=stream.period),
                SimToken(Packet(seq_id=packet.seq_id+1, stream_id=stream.stream_id, packet_time=0, mode_seq=packet.mode_seq), delay=stream.period),
                SimToken(stream, delay=stream.period),
                SimToken(packet)
            ]
        return [
            SimToken(mode),
            SimToken(stream),
            None
        ]

    return timer_function

def generate_packet_function_tw(stream):
    """

    """
    def timer_function(packet):
        return [
            SimToken(Packet(seq_id=packet.seq_id, stream_id=stream.stream_id, packet_time=0, mode_seq=packet.mode_seq)),
            SimToken(packet)
        ]
    return timer_function

def generate_nw_function(sched, precondition_rate):
    """
        method to simulate the network delay based on the schedule guarantee from json
    """
    def delay_function(mode, p):
        # TT network: streams not scheduled in the current network mode are dropped
        if p.stream_id not in mode.streams:
            return [SimToken(mode), None]

        now = p.packet_time
        st_id = p.stream_id
        rand = random.random()
        mode_id = str(mode.mode_id)

        expected = precondition_rate.get(str(st_id), {}).get("rate", None)
        if expected is None:
            return [SimToken(mode), None]

        if now > expected:
            return [SimToken(mode), None]

        # Avoid the hard coded index usage
        if rand <= sched.get(mode_id)[0]["prob"]:
            delay =  sched.get(mode_id)[0]["delay"]
        else:
            delay = sched.get(mode_id)[1]["delay"]

        return [
            SimToken(mode),
            SimToken(Packet(
                stream_id=p.stream_id,
                seq_id=p.seq_id,
                packet_time=p.packet_time+delay,
                mode_seq=p.mode_seq
            ), delay=delay)
        ]
    return delay_function


def generate_link_delay_function(link_delay):
    """
        method to simulate the link delay
        data fetched from json
    """
    def delay(packet):
        rand = random.random()
        if rand <= link_delay[0]["prob"]:
            delay = link_delay[0]["delay"]
        else:
            delay = link_delay[1]["delay"]
        return [SimToken(
            Packet(stream_id=packet.stream_id, 
                   seq_id=packet.seq_id,
                   packet_time=packet.packet_time+delay,
                   mode_seq=packet.mode_seq
                   ),
                   delay=delay
        )]
    return delay

def accept_condition(stream_id):
    def guard(packet):
        return packet.stream_id == stream_id
    return guard

def accept_condition_triggered(stream):
    def guard(packet):
        return packet.stream_id == stream.triggered_by
    return guard

def accept_nn_condition(stream_ids):
    frozen = frozenset(stream_ids)
    def guard(mode, packet):
        return packet.stream_id in frozen
    return guard

def compute_stream_nn_links(streams, nodes, links):
    """BFS: for each NN link (src_id, dst_id), find which stream IDs traverse it."""
    adj = defaultdict(list)
    for link in links:
        adj[link.src.node_id].append(link.dst.node_id)

    stream_on_link = defaultdict(set)
    for stream_id, stream in streams.items():
        start, end = stream.src.node_id, stream.dst.node_id
        if start == end:
            continue
        visited = {start}
        queue = deque([[start]])
        found = False
        while queue and not found:
            path = queue.popleft()
            curr = path[-1]
            for neighbor in adj[curr]:
                if neighbor == end:
                    full_path = path + [end]
                    for i in range(len(full_path) - 1):
                        u, v = full_path[i], full_path[i + 1]
                        if nodes[u].node_type == "NN":
                            stream_on_link[(u, v)].add(stream_id)
                    found = True
                    break
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
    return stream_on_link


def build_petri_net(
        network,
        nodes,
        modes,
        links,
        streams,
        sched,
        link_delays,
        precondition_rate
    ):

    places = defaultdict(dict)
    generate_events = list()
    done_events = list()
    stream_on_link = compute_stream_nn_links(streams, nodes, links)
    trigger_src_nodes = {
        st.src.node_id
        for st in streams.values()
        if st.triggered_by is not None
    }

    # Pre-compute which stream IDs have a triggered child stream.
    # Only these streams can rely on the triggered child's generate_event
    # to mark their done place. All others need an explicit done_event.
    streams_with_triggered_child = {
        st.triggered_by
        for st in streams.values()
        if st.triggered_by is not None
    }

    places[NETWORK_PLACE] = defaultdict(dict)
    places[STREAM_PLACE] = defaultdict(dict)
    for stream_id, stream in streams.items():
        src_node = stream.src
        dst_node = stream.dst
        if places.get(NETWORK_PLACE, {}).get(src_node.node_id) is None:
            places[NETWORK_PLACE][src_node.node_id] = NetworkPlace(
                node=network.add_var("p_"+str(src_node.node_id)+"_es")
            )

        if places.get(NETWORK_PLACE, {}).get(dst_node.node_id) is None:
            places[NETWORK_PLACE][dst_node.node_id] = NetworkPlace(
                node=network.add_var("p_"+str(dst_node.node_id)+"_es")
            )

        if places.get(STREAM_PLACE, {}).get(stream_id, None) is None:
            if stream.triggered_by is None:
                places[STREAM_PLACE][stream_id] = StreamPlace(
                    mode=network.add_var("p_"+str(stream_id)+"_mode"),
                    packet=network.add_var("p_"+str(stream_id)+"_packet"),
                    stream=network.add_var("p_"+str(stream_id) + "_stream"),
                    done=network.add_var("p_"+str(stream_id)+"_done")
                )

                event_name = "generate_event_"+str(stream_id)
                network.add_event(
                    [
                        places[STREAM_PLACE][stream_id].mode,
                        places[STREAM_PLACE][stream_id].packet,
                        places[STREAM_PLACE][stream_id].stream
                    ],
                    [
                        places[STREAM_PLACE][stream_id].mode,
                        places[STREAM_PLACE][stream_id].packet,
                        places[STREAM_PLACE][stream_id].stream,
                        places[NETWORK_PLACE][src_node.node_id].node
                    ],
                    behavior=generate_packet_function(modes),
                    name=event_name
                )
                generate_events.append(event_name)

                # Create a done_event unless a triggered child stream already
                # handles marking this stream's done place via its generate_event.
                if stream_id not in streams_with_triggered_child:
                    event_name = "done_event_"+str(stream_id)
                    network.add_event(
                        [
                            places[NETWORK_PLACE][dst_node.node_id].node
                        ],
                        [
                            places[STREAM_PLACE][stream_id].done
                        ],
                        behavior=lambda p: [SimToken(p)],
                        guard=accept_condition(stream_id),
                        name=event_name
                    )
                    done_events.append(event_name)
            else:
                places[STREAM_PLACE][stream_id] = StreamPlace(
                    triggered_by=network.add_var("pt_"+str(stream_id)+"_es"),
                    done=network.add_var("p_"+str(stream_id)+"_done")
                )

                event_name = "generate_event_"+str(stream_id)
                network.add_event(
                    [
                        places[NETWORK_PLACE][src_node.node_id].node
                    ],
                    [
                        places[STREAM_PLACE][stream_id].triggered_by,
                        places[STREAM_PLACE][stream.triggered_by].done
                    ],
                    behavior=generate_packet_function_tw(stream),
                    guard=accept_condition_triggered(stream),
                    name=event_name
                )
                generate_events.append(event_name)
                done_events.append(event_name)

                if dst_node.node_id not in trigger_src_nodes:
                    event_name = "done_event_"+str(stream_id)
                    network.add_event(
                        [
                            places[NETWORK_PLACE][dst_node.node_id].node
                        ],
                        [
                            places[STREAM_PLACE][stream_id].done
                        ],
                        behavior= lambda p: [SimToken(p)],
                        guard=accept_condition(stream_id),
                        name=event_name
                    )
                    done_events.append(event_name)

    for link in links:
        src, dest = link.src, link.dst
        if places.get(NETWORK_PLACE, {}).get(src.node_id) is None:
            places[NETWORK_PLACE][src.node_id] =  NetworkPlace(
                node=network.add_var("nn_"+str(src.node_id)),
                mode=network.add_var("nn_"+str(src.node_id)+"_mode")
            )
        if places.get(NETWORK_PLACE, {}).get(dest.node_id, None) is None:
            places[NETWORK_PLACE][dest.node_id] = NetworkPlace(
                node=network.add_var("nn_"+str(dest.node_id)),
                mode=network.add_var("nn_"+str(dest.node_id)+"_mode")
            )

        
        if src.node_type == "NN":
            event_name = "t_NN_" + str(src.node_id) + "_" + str(dest.node_id)
            allowed = stream_on_link.get((src.node_id, dest.node_id), set())
            network.add_event(
                inflow=[
                    places[NETWORK_PLACE][src.node_id].mode,
                    places[NETWORK_PLACE][src.node_id].node
                ],
                outflow=[
                    places[NETWORK_PLACE][src.node_id].mode,
                    places[NETWORK_PLACE][dest.node_id].node
                ],
                behavior=generate_nw_function(sched, precondition_rate),
                # guard=accept_nn_condition(allowed),
                name = event_name
            )
            
        else:
            print(src, dest)
            for stream_id, stream in streams.items():
                if stream.src.node_id == src.node_id:
                    event_name = "t_es_"+str(stream_id)
                    if stream.triggered_by is not None and streams.get(stream.triggered_by).dst.node_id == src.node_id:
                        network.add_event(
                            inflow=[
                                places[STREAM_PLACE][stream_id].triggered_by
                            ],
                            outflow=[
                                places[NETWORK_PLACE][dest.node_id].node
                            ],
                            behavior=generate_link_delay_function(link_delay=link_delays),
                            guard=accept_condition(stream_id=stream_id),
                            name=event_name
                        )
                        generate_events.append(event_name)
                    else:
                        network.add_event(
                            inflow=[
                                places[NETWORK_PLACE][src.node_id].node
                            ],
                            outflow=[
                                places[NETWORK_PLACE][dest.node_id].node
                            ],
                            behavior=generate_link_delay_function(link_delay=link_delays),
                            guard=accept_condition(stream_id=stream_id),
                            name=event_name
                        )

    
    return places, generate_events, done_events


def run_simulation(nodes, 
                   links, 
                   streams, 
                   modes, 
                   mode_switch, 
                   sched, 
                   switch_class, 
                   link_delays, 
                   precondition_rate,
                   delivery_constraints
                    ):
    """
    Docstring for run_simulation
    
    :param nodes: Description
    :param links: Description
    :param streams: Description
    :param modes: Description
    :param mode_switch: Description
    :param sched: Description
    """
    network = SimProblem()
    places, generate_events, done_events = build_petri_net(
        network,
        nodes,
        modes,
        links,
        streams,
        sched,
        link_delays,
        precondition_rate
    )
    
    # Init current mode
    current_mode_id, time = mode_switch.popleft()
    mode = modes.get(current_mode_id)

    logger.info(f"Current mode: {current_mode_id}")
    for st in mode.streams:
        # Only initialize periodic streams (those without triggered_by)
        # Triggered streams don't have mode/packet/stream places
        if streams.get(st).triggered_by is None:
            places[STREAM_PLACE][st].mode.put(mode)
            places[STREAM_PLACE][st].packet.put(
                Packet(
                    seq_id=1, stream_id=st, packet_time=0, mode_seq=str(current_mode_id)+"@" + str(time)
                )
            )
            places[STREAM_PLACE][st].stream.put(
                streams.get(st)
            )

    for key in places[NETWORK_PLACE].keys():
        if nodes.get(key).node_type == "NN":
            places[NETWORK_PLACE][key].mode.put(mode)

    
    reporter = TimesReporter(set(generate_events), set(done_events), streams=streams, delivery_constraints=delivery_constraints)
    sync_switch = switch_class(
        modes=modes,
        streams=streams,
        places=places,
        nodes=nodes,
        mode_switch=mode_switch,
    )
    active_model = True

    # Visualisation(network).show()
    while network.clock < 20 and active_model:
        bindings = network.bindings()
        if sync_switch.check_app_switch(network_clock=network.clock):
            sync_switch.app_switch(network_clock=network.clock)
            bindings = network.bindings()
        if sync_switch.check_net_switch(network_clock=network.clock):
            sync_switch.net_switch(network_clock=network.clock)
            bindings = network.bindings()
            
        
        # logger.info(f"{bindings} {network.clock}")
        if len(bindings) > 0:
            timed_binding = network.binding_priority(bindings)
            network.fire(timed_binding)
            if reporter is not None:
                reporter.callback(timed_binding)
        else:
            active_model = False

    return reporter    

def main():
    """
    Docstring for main
    """
    logger.info("starting petri net - network simulator")
    parser = argparse.ArgumentParser(
        prog="Petri Net - Network Simulator",
    )
    parser.add_argument(
        "-f", 
        "--file",
        required=True
    )
    parser.add_argument(
        "-s",
        "--strategy",
        required=True
    )
    parser.add_argument(
        "-b",
        "--benchmark",
        required=False
    )
    args = parser.parse_args()
    nw_model_file = args.file
    logger.info("fetching network model from %s", nw_model_file)

    strategy = args.strategy
    if strategy == "Sync":
        switch_class = SynchSwitch
    elif strategy == "Delay":
        switch_class = DelayedSwitch
    else:
        logger.info("Invalid switch strategy")
        exit(1)
    data = load_data(nw_model_file)   
    if data is None:
        close_pgm()
    (nodes, 
     links, 
     streams, 
     modes, 
     sched, 
     mode_switch, 
     link_delays, 
     precondition_rate, 
     delivery_constraints) = load_network(data=data)
    
    if args.benchmark is None:
        reporter = run_simulation(
            nodes=nodes,
            links=links,
            streams=streams,
            modes=modes,
            sched=sched,
            mode_switch=mode_switch.copy(),
            switch_class=switch_class,
            link_delays=link_delays,
            precondition_rate=precondition_rate,
            delivery_constraints=delivery_constraints
        )
        logger.info(f"report for {switch_class.name}")
        reporter.e2e_validate()
        reporter.validate_throuput()
        reporter.write()

        # Build plant_streams mapping for dual-pendulum trace generation
        plant_streams = defaultdict(lambda: {'sensor': [], 'control': []})
        for st_id, st in streams.items():
            if st.plant_id is not None:
                if st.triggered_by is None:
                    # Sensor stream (has period, no triggered_by)
                    plant_streams[st.plant_id]['sensor'].append(st_id)
                else:
                    # Control stream (triggered by sensor)
                    plant_streams[st.plant_id]['control'].append(st_id)

        if plant_streams:
            reporter.write_plant_traces(dict(plant_streams))
    else:
        N = int(args.benchmark)
        window_violations = 0
        control_violations = 0
        deadline_miss_sum = 0.0
        max_interrupt_list = []
        
        for itr in range(1, N+1):
            reporter = run_simulation(
                nodes=nodes,
                links=links,
                streams=streams,
                modes=modes,
                sched=sched,
                mode_switch=mode_switch.copy(),
                switch_class=switch_class,
                link_delays=link_delays,
                precondition_rate=precondition_rate,
                delivery_constraints=delivery_constraints
            )
            logger.info(f"report for {switch_class.name}")
            reporter.e2e_validate()
            if reporter.validate_throuput():
                window_violations += 1
            
        window_violation_prob = window_violations / N
        control_violation_prob = control_violations / N
        mean_deadline_miss = deadline_miss_sum / N
        mean_interrupt = sum(max_interrupt_list) / N
        
        p = window_violation_prob
        ci = 1.96 * math.sqrt(p * (1 - p) / N)

        results = {
        "N": N,
        "window_violation_probability": p,
        "ci_lower": p - ci,
        "ci_upper": p + ci,
        "control_violation_probability": control_violation_prob,
        "mean_deadline_miss": mean_deadline_miss,
        "mean_interrupt": mean_interrupt
        }
        print(results)



if __name__ == "__main__":
    main()
