from simpn.simulator import SimProblem, SimVar, SimVarQueue, SimToken
from simpn.visualisation import Visualisation

net = SimProblem()

es1 = net.add_var("es1")
nn = net.add_var("nn")
es3 = net.add_var("es3")
es1.put("m1")

def delay(token, queue):
    print(queue)
    queue.add_token(SimToken(token.value, token.time+0.5))
    return [queue]

net.add_event(
    [es1, nn.queue],
    [nn.queue],
    delay
)


vis = Visualisation(net)
vis.show()