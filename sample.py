from simpn.simulator import SimProblem
from simpn.simulator import SimToken
from simpn.visualisation import Visualisation
from random import expovariate as exp
import simpn.prototypes as prototype
from simpn.prototypes_queueing import QueueingGenerator, QueueingQueue, QueueingServer, QueueingSink, QueueingChoice

# Instantiate a simulation problem.
network = SimProblem()

end_system1 = network.add_var("end_system1")
network_node = network.add_var("network_node")
end_system3 = network.add_var("end_system3")

prototype.BPMNStartEvent(network, [], [end_system1], "message", 10)

# Model the storage elements.
q1 = QueueingQueue(network, "q1")
# q2 = QueueingQueue(network, "q2")
# q3 = QueueingQueue(network, "q3")


sink1 = QueueingSink(network, "sink1")
# sink2 = QueueingSink(network, "sink2")
# sink3 = QueueingSink(network, "sink3")
def delay(token):
    return [SimToken(token, delay=10)]
network.add_event([end_system1], [network_node], delay)

def q_delay(queue):
    if len(queue) > 1:
        return [queue[0], queue[1:]]
    return [None, queue]


# Model the flow elements.
# g1 = QueueingGenerator(network, [], [q1], "g1", lambda: exp(1/10))

s1 = QueueingServer(network, [network_node], [q1], "s1", lambda: 0, c=10)

# choice = QueueingChoice(network, [pre_choice], [q2, q3], "choice", [50, 50])
# network.add_event([q1], [sink1, q1], q_delay)
s2 = QueueingServer(network, [q1], [sink1], "s2", lambda: 10, c=10)

# s3 = QueueingServer(network, [q3], [sink3], "s3", lambda: exp(1/9))

# Visualise the simulation problem.
m = Visualisation(network)
m.show()