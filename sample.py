import random
from simpn.simulator import SimProblem, SimToken
import simpn.prototypes as prototype
# from simpn.reporters import SimpleReporter
from reporter.time_reporter import TimesReporter
from models.token import SimVarMonitor
from simpn.visualisation import Visualisation

network = SimProblem()
net_cfg = network.add_var("net_cfg")

p_mode1 = network.add_var("mode1")
p_timer1 = network.add_var("p_timer1")
p_ES1 = network.add_var("p_ES1")

p_mode2 = network.add_var("mode2")
p_timer2 = network.add_var("p_timer2")
p_ES2 = network.add_var("p_ES2")
p_net_buff = network.add_var("p_network_buffer")
p_ES3 = network.add_var("p_ES3")
# p_ES3 = SimVarMonitor("p_ES3", release_time=0, network=network)
p_done = network.add_var("p_done")
# network.add_prototype_var(p_ES3)
# p_mode = network.add_var("mode")

p_mode1.put(1)
net_cfg.put(1)
p_timer1.put("p1-0")
p_timer2.put("p2-0")

def timer(p, mode):
    if mode == 1 or mode == 2:
        return [SimToken(p[:-1]+str(int(p[len(p)-1]) + 1), delay=20), SimToken(mode), SimToken(p)]
    return [SimToken(p), SimToken(mode), None]


def timer2(p, mode):
    if mode == 2:
        return [SimToken(p[:-1]+str(int(p[len(p)-1]) + 1), delay=20), SimToken(mode), SimToken(p)]
    return [SimToken(p), SimToken(mode), None]

def delay(p):
    return [SimToken(p, delay=10)]

def delay2(p, mode):
    rand = random.random()
    if mode == 1:
        d = 10 if rand <= 0.9 else 20
        return [SimToken(p, delay=d), SimToken(mode)]
    elif mode == 2:
        d = 5 if rand <= 0.9 else 10
        return [SimToken(p, delay=d), SimToken(mode)]

def dummy(p):
    return [SimToken(p)]

network.add_event([p_timer1, p_mode1], [p_timer1, p_mode1, p_ES1], timer, name="t_generate_p1")
network.add_event([p_timer2, p_mode2], [p_timer2, p_mode2, p_ES2], timer2, name="t_generate_p2")
network.add_event([p_ES1], [p_net_buff], delay, name="to_net-buff1")
network.add_event([p_ES2], [p_net_buff], delay, name="to_net-buff2")
network.add_event([p_net_buff, net_cfg], [p_ES3, net_cfg], delay2, name="to_es3")
network.add_event([p_ES3], [p_done], dummy, name="to_done")

reporter = TimesReporter()
active_model = True

while network.clock <= 200 and active_model:
    bindings = network.bindings()
    if len(bindings) > 0:
        timed_binding = network.binding_priority(bindings)

        if network.clock == 100:
            cfg_list = [token for token in p_mode1.marking if token.value == 1]
            if len(cfg_list) != 0:
                for tk in cfg_list:
                    p_mode1.remove_token(tk)

            p_mode1.add_token(SimToken(2, time=100))
            p_mode2.add_token(SimToken(2, time=100))
           
        if network.clock == 130:
            cfg_list = [token for token in net_cfg.marking if token.value == 1]
            if len(cfg_list) != 0:
                for tk in cfg_list:
                    net_cfg.remove_token(tk)
            net_cfg.add_token(SimToken(2, time=130))

        network.fire(timed_binding)
        # print(bindings)
        if reporter is not None:
            reporter.callback(timed_binding)
    else:
        active_model = False

reporter.validate()
Visualisation(network).show()
