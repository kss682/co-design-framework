from cpnpy.cpn.colorsets import ColorSetParser
from cpnpy.cpn.cpn_imp import Place
from cpnpy.cpn.cpn_imp import Marking
from cpnpy.cpn.cpn_imp import Transition
from cpnpy.cpn.cpn_imp import Arc
from cpnpy.cpn.cpn_imp import CPN
from cpnpy.cpn.cpn_imp import EvaluationContext
from cpnpy.analysis.analyzer import StateSpaceAnalyzer

# Colour sets
cs_defs = """
colset DOT = string timed;
colset MESSAGE = { 'M1', 'M2' } timed;
colset MESSAGE_Q = list MESSAGE;
"""

parser = ColorSetParser()
colsets = parser.parse_definitions(cs_defs)
message_set = colsets["MESSAGE"]
dot_set = colsets["DOT"]
message_q_set = colsets["MESSAGE_Q"]
# # Places
end_system1 = Place("ES1", message_set)
end_system3 = Place("ES3", message_set)
# end_system2 = Place("ES2", message_set)
network_node = Place("NN", message_q_set)

# # Markings
periodic = [i for i in range(0, 30, 10)]
marking = Marking()
marking.set_tokens("ES1", ["M1"]*3, periodic)
# marking.set_tokens("ES2", ["M2"], [20])
marking.set_tokens("NN", [[]])
# # Transition and Gaurds
ES1_to_NN = Transition(
    "ES1_to_NN", 
    variables=["MESSAGE", "MESSAGE_Q"],
    transition_delay=10
)
arc_in = Arc(
    end_system1,
    ES1_to_NN,
    "MESSAGE"
)
arc_out = Arc(
    ES1_to_NN,
    network_node,
    "MESSAGE_Q + [MESSAGE]",
)
arc_back = Arc(
    network_node,
    ES1_to_NN,
    "MESSAGE_Q"
)


# ES2_to_NN = Transition(
#     "ES2_to_NN",
#     variables=["MESSAGE", "MESSAGE_Q"],
#     transition_delay=10
# )
# arc_in1 = Arc(
#     end_system2,
#     ES2_to_NN,
#     "MESSAGE"
# )
# arc_out1 = Arc(
#     ES2_to_NN,
#     network_node,
#     "MESSAGE_Q + [MESSAGE]"
# )
# arc_outback1 = Arc(
#     network_node,
#     ES2_to_NN,
#     "MESSAGE_Q"
# )

NN_to_ES3 = Transition(
    "NN_to_ES3",
    variables=["MESSAGE_Q", "MESSAGE"],
    transition_delay=10
)
arc_in2 = Arc(
    network_node,
    NN_to_ES3,
    "MESSAGE_Q[0]"
)
arc_out2 = Arc(
    NN_to_ES3,
    end_system3,
    "MESSAGE"
)
arc_outback2 = Arc(
    NN_to_ES3,
    network_node,
    "MESSAGE_Q[1:] if len(MESSAGE_Q) > 1 else []"
)

# # Arc and Expression
cpn = CPN()
cpn.add_place(end_system1)
cpn.add_place(end_system3)
# cpn.add_place(end_system2)
cpn.add_place(network_node)

cpn.add_transition(ES1_to_NN)
# cpn.add_transition(ES2_to_NN)
cpn.add_transition(NN_to_ES3)

cpn.add_arc(arc_in)
cpn.add_arc(arc_out)
cpn.add_arc(arc_back)
# cpn.add_arc(arc_in1)
# cpn.add_arc(arc_out1)
# cpn.add_arc(arc_outback1)
cpn.add_arc(arc_in2)
cpn.add_arc(arc_out2)
cpn.add_arc(arc_outback2)
# import json
# from cpnpy.cpn.importer import import_cpn_from_json

# with open("periodic_message.json", "r") as f:
#     data = json.load(f)
# cpn, marking, context = import_cpn_from_json(data)
context = EvaluationContext()
print(marking)
print(cpn)
while True:
    transitions = list(cpn.transitions)
    enabled_transitions = []
    
    for trn in transitions:
        if cpn.is_enabled(trn, marking, context):
            print("Before firing t:", marking)
            cpn.fire_transition(trn, marking, context)
            print("After firing t:", marking)

    old_clock = marking.global_clock
    cpn.advance_global_clock(marking)
    print("After advancing clock:", marking.global_clock)
    if old_clock == marking.global_clock:
        print("Done")
        break
