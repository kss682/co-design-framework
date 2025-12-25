import argparse
import json
import logging
import random
from collections import defaultdict
from models.node import Node
from models.links import Link
from models.stream import Stream
from models.mode import Mode
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
    modes:list = []

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
                _src=nodes.get(stm.get("src")),
                _dst=nodes.get(stm.get("dst")),
                _type=stm.get("type"),
                _release_time=stm.get("release_time"),
                _period=stm.get("period"),
                _deadline=stm.get("deadline")
            )
    logger.info(" %s streams found in the network", len(streams))

    for mode_id in data.get("modes").keys():
        mode = data.get("modes")[mode_id]
        logger.info("%s", mode)
        modes.append(
            Mode(
             _id=int(mode_id),
             _name=mode.get("name"),
             _streams=mode.get("streams"),
             _schedule=mode.get("schedule_id")
            )
        )
    logger.info(" %s modes found in the network", len(modes))
    
    schedules = data.get("schedules")
    sim_config = data.get("simulation")
    return nodes, links, streams, modes, schedules, sim_config


def close_pgm():
    """
    Docstring for close_pgm
    
    :return: Description
    :rtype: NoReturn
    """
    logger.info("closing simulation due to error")
    exit(1)


def generate_packet_function(mode_list):
    def timer_function(mode, p):
        for ob in mode_list:
            if mode._id == ob._id and p._id in ob.streams:
                return [
                    SimToken(mode),
                    SimToken(p, delay=p.period),
                    SimToken(p)
                ]
        return [
            SimToken(mode),
            SimToken(p),
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
    nodes, links, streams, modes, sched, sim_config = load_network(data=data)
    
    # network = SimProblem()
    # logger.info("%s", streams)
    network = SimProblem()

    places = defaultdict(dict)
    for _id, stream in streams.items():
        src_node = stream.src
        places[src_node._id]["mode"] = network.add_var("p_"+str(src_node._id)+"_mode")
        places[src_node._id]["timer"] = network.add_var("p_"+str(src_node._id)+"_timer")
        places[src_node._id]["node"] = network.add_var("p_"+str(src_node._id)+"_es")
        network.add_event(
            [places[src_node._id]["mode"], places[src_node._id]["timer"]],
            [places[src_node._id]["mode"], places[src_node._id]["timer"], places[src_node._id]["node"]],
            generate_packet_function(modes),
            name="t_generate_"+str(stream._id)
        )
        
        dst_node = stream.dst
        if places.get(dst_node._id, None) is None:
            places[dst_node._id]["node"] = network.add_var("p_"+str(dst_node._id)+"_es")
            places[dst_node._id]["done"] = network.add_var("p_"+str(dst_node._id)+"_done")
            network.add_event(
                [places[dst_node._id]["node"]],
                [places[dst_node._id]["done"]],
                lambda p: [SimToken(p)],
                name="to_done_"+str(dst_node._id)
            )

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


    for mode in modes:
        if mode._id == sim_config.get("init"):
            for st in mode.streams:
                places[st]["mode"].put(mode)
                places[st]["timer"].put(streams.get(st))
            for key, place in places.items():
                if nodes.get(key)._type == "NN":
                    place["mode"].put(mode)

    reporter = TimesReporter()
    active_model = True
    switch_time = sim_config.get("switch_time")
    is_switch_mode = True
    is_net_reconfig = True
    reconfig_delay = sim_config.get("net_reconfig_delay")

    while network.clock <= sim_config.get("sim_time") and active_model:
        bindings = network.bindings()
        if len(bindings) > 0:
            timed_binding = network.binding_priority(bindings)

            network.fire(timed_binding)
            if network.clock == switch_time:
                logger.info("Mode switch triggered at %s", switch_time)
                for _id, stream in streams.items():
                    cfg_list = [token for token in places[stream.src._id]["mode"].marking if token.value._id == 1]
                    if len(cfg_list) != 0:
                        places[src._id]["mode"].marking.clear()
                    print(cfg_list)
                    # exit(1)
                    if _id in modes[1].streams:
                        places[stream.src._id]["mode"].add_token(SimToken(modes[1], time=switch_time))
                        places[stream.src._id]["timer"].add_token(SimToken(stream, time=switch_time))
                
            
            if network.clock >= switch_time + reconfig_delay and is_net_reconfig:
                logger.info("network reconfig triggered at %s", network.clock)
                for _id, node in nodes.items():
                    if node._type == "NN":
                        cfg_list = [token for token in places[_id]["mode"].marking if token.value._id == sim_config.get("init")]
                        if len(cfg_list) != 0:
                            for tk in cfg_list:
                                places[_id]["mode"].remove_token(tk)
                        print(modes[1]._id)
                        places[_id]["mode"].add_token(SimToken(modes[1], time=switch_time+reconfig_delay))
                is_net_reconfig = False


            
            # print(bindings)
            if reporter is not None:
                reporter.callback(timed_binding)
        else:
            active_model = False

    # reporter.validate()
    vis = Visualisation(network)
    vis.show()




if __name__ == "__main__":
    main()
