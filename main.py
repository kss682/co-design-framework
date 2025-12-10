import argparse
import json
import logging
from models.node import Node
from models.links import Link
from models.stream import Stream

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
    nodes:list = {}
    links:list = []
    streams:list = []
    
    # Need to extract this out into a validation function that does strict checking on the json
    if data.get('nodes', None) is None or data.get('links', None) is None or data.get('streams', None) is None:        
        logger.info("missing information in json, please validate")
        close_pgm()

    for node in data.get("nodes"):
        nodes[node.get("id")] = Node(
                _id=node.get('id'),
                _type=node.get('type')
            )

    logger.info("%s nodes found in the network", len(nodes))

    for lnk in data.get('links'):
        links.append(
            Link(
                _src=nodes.get(lnk.get("src")),
                _dst=nodes.get(lnk.get("dst"))
            )
        )

    logger.info("%s links found in the network", len(links))

    for stm in data.get('streams'):
        streams.append(
            Stream(
                _id=stm.get("id"),
                _src=nodes.get(stm.get("src")),
                _dst=nodes.get(stm.get("dst")),
                _release_time=stm.get("release_time"),
                _period=stm.get("period"),
                _deadline=stm.get("deadline")
            )
        )
    logger.info("%s streams found in the network", len(streams))
    return nodes, links, streams


def close_pgm():
    """
    Docstring for close_pgm
    
    :return: Description
    :rtype: NoReturn
    """
    logger.info("closing simulation due to error")
    exit(1)


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
    nodes, links, streams = load_network(data=data)
    

if __name__ == "__main__":
    main()
