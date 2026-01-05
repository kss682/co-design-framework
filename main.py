import argparse
import json
import logging
import random
from collections import defaultdict
from collections import deque

from models.node import Node
from models.links import Link
from models.stream import Stream, Packet, Timer
from models.mode import Mode
from switch_module.synchronized_switch import SynchSwitch
from reporter.time_reporter import TimesReporter
from simpn.simulator import SimProblem, SimToken
from simpn.visualisation import Visualisation


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# DATA:dict = {}


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

    logger.info(" %s nodes found in the network", len(nodes))

    for lnk in data.get('links'):
        links.append(
            Link(
                _src=nodes.get(lnk.get("src")),
                _dst=nodes.get(lnk.get("dst"))
            )
        )

    logger.info(" %s links found in the network", len(links))

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
    logger.info(" %s streams found in the network", len(streams))

    for mode_id in data.get("modes").keys():
        mode = data.get("modes")[mode_id]
        logger.info("%s", mode)
        modes[int(mode_id)] = Mode(
             _id=int(mode_id),
             _name=mode.get("name"),
             _streams=mode.get("streams"),
             _schedule=mode.get("schedule_id")
            )
    logger.info(" %s modes found in the network", len(modes))
    
    schedules = data.get("schedules")
    mode_switch = data.get("mode_switch")
    print(mode_switch)
    return nodes, links, streams, modes, schedules, deque(mode_switch)


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
                SimToken(Packet(seq_id=packet.seq_id+1, stream_id=stream._id), delay=stream.period),
                SimToken(stream, delay=stream.period),
                SimToken(packet)
            ]
        return [
            SimToken(mode),
            SimToken(stream),
            None
        ]

    return timer_function


def generate_nw_function(sched):
    def delay_function(mode, p):
        rand = random.random()
        mode_id = str(mode._id)
        if rand <= sched.get(mode_id)[0]["prob"]:
            delay =  sched.get(mode_id)[0]["delay"]
        else:
            delay = sched.get(mode_id)[1]["delay"]
        return [
            SimToken(mode),
            SimToken(p, delay=delay)
        ]
    return delay_function


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
    nodes, links, streams, modes, sched, mode_switch = load_network(data=data)
    print(mode_switch)
    network = SimProblem()

    places = defaultdict(dict)
    generate_events = list()
    done_events = list()

    for _id, stream in streams.items():
        src_node = stream.src
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

        if places.get(dest._id, None) is None:
            places[dest._id]["node"] = network.add_var("nn_"+str(dest._id))
            places[dest._id]["mode"] = network.add_var("nn_"+str(dest._id)+"_mode")
        
        if src._type == "NN":
            network.add_event(
                [places[src._id]["mode"], places[src._id]["node"]],
                [places[src._id]["mode"], places[dest._id]["node"]],
                generate_nw_function(sched),
                name = "t_NN_"+str(src._id)
            )
        else:
            network.add_event(
                [places[src._id]["node"]],
                [places[dest._id]["node"]],
                lambda p: [SimToken(p)],
                name="t_es_"+str(src._id)
            )

    # Init current mode
    current_mode_id, time = mode_switch.popleft()
    print(current_mode_id, time)
    mode = modes.get(current_mode_id)
    print(mode)
    for st in mode.streams:
        places[st]["mode"].put(mode)
        places[st]["packet"].put(Packet(seq_id=1, stream_id=st))
        places[st]["stream"].put(streams.get(st))

    for key, place in places.items():
        if nodes.get(key)._type == "NN":
            place["mode"].put(mode)

    
    reporter = TimesReporter(set(generate_events), set(done_events), streams=streams)
    sync_switch = SynchSwitch(
        modes=modes, 
        streams=streams,
        places=places,
        nodes=nodes, 
        mode_switch=mode_switch
    )
    active_model = True
    app_switch = True
    net_switch = True

    while network.clock <= 500 and active_model:
        if sync_switch.check_switch(network_clock=network.clock):
            logger.info("Mode switch triggered at %s", network.clock)
            sync_switch.switch(network_clock=network.clock)

        bindings = network.bindings()
        if len(bindings) > 0:
            timed_binding = network.binding_priority(bindings)
            network.fire(timed_binding)
            if reporter is not None:
                reporter.callback(timed_binding)
        else:
            active_model = False

    reporter.e2e_validate()
    vis = Visualisation(network)
    vis.show()




if __name__ == "__main__":
    main()
