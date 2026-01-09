import argparse
import json
import random
from collections import defaultdict
from collections import deque

from loguru import logger
from models.node import Node
from models.links import Link
from models.stream import Stream, Packet, Timer
from models.mode import Mode
from switch_module.synchronized_switch import SynchSwitch
from switch_module.delayed_switch import DelayedSwitch
from reporter.time_reporter import TimesReporter
from reporter.delivery_constraints import PacketDeliveryConstraints
from simpn.simulator import SimProblem, SimToken
from simpn.visualisation import Visualisation

# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

SWITCH_STRATEGY = [
    SynchSwitch,
    DelayedSwitch
]


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
                _id=node.get('id'),
                _type=node.get('type')
            )

    logger.info(f"{len(nodes)} nodes found in the network", len(nodes))

    for lnk in data.get('links'):
        links.append(
            Link(
                _src=nodes.get(lnk.get("src")),
                _dst=nodes.get(lnk.get("dst"))
            )
        )

    logger.info(f"{len(links)} links found in the network")

    for stm in data.get('streams'):
        streams[stm.get("id")] = Stream(
                _id=stm.get("id"),
                src=nodes.get(stm.get("src")),
                dst=nodes.get(stm.get("dst")),
                traffic_type=stm.get("type"),
                release_time=stm.get("release_time"),
                period=stm.get("period"),
                deadline=stm.get("deadline")
            )
    logger.info(f" {len(streams)} streams found in the network")

    for mode_id in data.get("modes").keys():
        mode = data.get("modes")[mode_id]
        logger.info("%s", mode)
        modes[int(mode_id)] = Mode(
             _id=int(mode_id),
             _name=mode.get("name"),
             _streams=mode.get("streams"),
             _schedule=mode.get("schedule_id")
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
    def timer_function(mode, packet, stream):

        if mode_dict.get(mode._id, None) is not None and stream._id in mode_dict.get(mode._id).streams:
                # current_birthtime = stream.birthtime
                # stream.reset_birthtime()
            return [        
                SimToken(mode, delay=stream.period),
                SimToken(Packet(seq_id=packet.seq_id+1, stream_id=stream._id, packet_time=0, mode_seq=packet.mode_seq), delay=stream.period),
                SimToken(stream, delay=stream.period),
                SimToken(packet)
            ]
        return [
            SimToken(mode),
            SimToken(stream),
            None
        ]

    return timer_function


def generate_nw_function(sched, precondition_rate, packet_last_seen):
    def delay_function(mode, p):
        now = p.packet_time
        st_id = p.stream_id
        rand = random.random()
        mode_id = str(mode._id)

        expected = precondition_rate.get(str(st_id)).get("rate", None)
        if expected is None:
            return [SimToken(mode), None]

        # prev = packet_last_seen.get(mode_id, {}).get(st_id, None)
        # logger.info(f"{prev}: {now}: {expected}")
        if now > expected:
            return [SimToken(mode), None]

        # packet_last_seen[mode_id][st_id] = now
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


def build_petri_net(
        network,
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

    for _id, stream in streams.items():
        src_node = stream.src
        if places.get(src_node._id, None) is None:
            places[src_node._id]["mode"] = network.add_var("p_"+str(src_node._id)+"_mode")
            places[src_node._id]["packet"] = network.add_var("p_"+str(src_node._id)+"_packet")
            places[src_node._id]["stream"] = network.add_var("p_"+str(src_node._id) + "_stream")
            places[src_node._id]["node"] = network.add_var("p_"+str(src_node._id)+"_es")
            event_name = "t_generate_"+str(stream._id)
            network.add_event(
                [places[src_node._id]["mode"], places[src_node._id]["packet"], places[src_node._id]["stream"]],
                [places[src_node._id]["mode"], places[src_node._id]["packet"], places[src_node._id]["stream"],places[src_node._id]["node"]],
                generate_packet_function(modes),
                name=event_name
            )
            generate_events.append(event_name)
        
        dst_node = stream.dst
        if places.get(dst_node._id, None) is None:
            places[dst_node._id]["node"] = network.add_var("p_"+str(dst_node._id)+"_es")
            places[dst_node._id]["done"] = network.add_var("p_"+str(dst_node._id)+"_done")
            event_name="to_done_"+str(dst_node._id)
            network.add_event(
                [places[dst_node._id]["node"]],
                [places[dst_node._id]["done"]],
                lambda p: [SimToken(p)],
                name=event_name
            )
            done_events.append(event_name)

    for link in links:
        src, dest = link.src, link.dst
        if places.get(src._id, None) is None:
            places[src._id]["node"] = network.add_var("nn_"+str(src._id))
            places[src._id]["mode"] = network.add_var("nn_"+str(src._id)+"_mode")
            places[src._id]["packet_last_seen"] = defaultdict(dict)
        if places.get(dest._id, None) is None:
            places[dest._id]["node"] = network.add_var("nn_"+str(dest._id))
            places[dest._id]["mode"] = network.add_var("nn_"+str(dest._id)+"_mode")
            places[dest._id]["packet_last_seen"] = defaultdict(dict)

        if src._type == "NN":
            network.add_event(
                [places[src._id]["mode"], places[src._id]["node"]],
                [places[src._id]["mode"], places[dest._id]["node"]],
                generate_nw_function(sched, precondition_rate, places[src._id]["packet_last_seen"]),
                name = "t_NN_"+str(src._id)
            )
        else:
            network.add_event(
                [places[src._id]["node"]],
                [places[dest._id]["node"]],
                generate_link_delay_function(link_delay=link_delays),
                name="t_es_"+str(src._id)
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

    # import pdb
    # breakpoint()
    for st in mode.streams:
        places[st]["mode"].put(mode)
        places[st]["packet"].put(Packet(seq_id=1, stream_id=st, packet_time=0, mode_seq=str(current_mode_id)+"@" + str(time)))
        places[st]["stream"].put(streams.get(st))

    for key, place in places.items():
        if nodes.get(key)._type == "NN":
            place["mode"].put(mode)

    
    reporter = TimesReporter(set(generate_events), set(done_events), streams=streams, delivery_constraints=delivery_constraints)
    sync_switch = switch_class(
        modes=modes, 
        streams=streams,
        places=places,
        nodes=nodes, 
        mode_switch=mode_switch,

    )
    active_model = True

    while network.clock <= 500 and active_model:
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
    Visualisation(network).show()
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
    args = parser.parse_args()
    nw_model_file = args.file
    logger.info("fetching network model from %s", nw_model_file)

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
    
    for switch_class in SWITCH_STRATEGY:
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




if __name__ == "__main__":
    main()
