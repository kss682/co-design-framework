import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp
from loguru import logger

# Define pendulum constants
m = 0.2 # mass of pendulum
M = 0.5 # mass of cart
l = 0.3 # length of pendulum 
I = m*pow((2*l),2)/12 # Moment of inertia (COM) [m*(2l)ˆ2]/12
J = I + m*l*l # 0.006 + 0.2*0.3*0.3 Icom + mlˆ2 (Parallel axis theorm)
g = 9.8

D_denom = (M+m)*J - (m*m*l*l)
A = np.array([
    [0, 1, 0, 0],
    [0, 0, -1*(m*m*g*l*l)/D_denom, 0],
    [0, 0, 0, 1],
    [0, 0, (M+m)*m*g*l/D_denom, 0]
])

B = np.array([
    [0],
    [(J)/D_denom],
    [0],
    [-1*m*l/D_denom]
])
C = np.eye(4)
D = np.zeros((4,1))


def run_event_simulation(trace_file, A, B, gains_dict, x0, target_x):
    df = pd.read_csv(trace_file)
    
    t_curr = 0
    x_curr = np.array(x0, dtype=float)
    
    u_active = 0.0
    u_pending = 0.0
    x_sampled = np.zeros(4)
    K_active = gains_dict[1]
    
    history = []
    
    for _, row in df.iterrows():
        t_event = row['t']
        event = row['event_type']
        mode = row['mode']
        
        if t_event > t_curr:
            t_grid = np.arange(t_curr, t_event, 0.001)
            t_grid = t_grid[t_grid < t_event]
            t_grid = np.append(t_grid, t_event)
            sol = solve_ivp(
                lambda t, y: A @ y + (B @ [u_active]).flatten(),
                [t_curr, t_event], x_curr, method='RK45',
                t_eval=t_grid
            )
            for i in range(sol.t.shape[0] - 1):
                history.append([sol.t[i], *sol.y[:, i]])
            x_curr = sol.y[:, -1]
            t_curr = t_event
        
        if event == 'plantsend':
            x_sampled = x_curr.copy()
            
        elif event == 'controllerreceive':
            K_active = gains_dict[mode]
            error = target_x - x_sampled
            u_pending = np.dot(K_active, error)
            u_active = u_pending
        # elif event == 'plantreceive':
            
        
        history.append([t_curr, *x_curr])
    
    return pd.DataFrame(history, columns=['t', 'p', 'v', 'theta', 'omega'])


def main():
    """
    """
    parser = argparse.ArgumentParser(
        prog="Pendulum simulator",
    )
    parser.add_argument(
        "-f",
        "--file",
        required=True
    )
    parser.add_argument(
        "-x",
        "--x0",
        required=False,
        help="Initial state as comma-separated values, e.g. '0.01,0.0,0.1,0.5'"
    )
    parser.add_argument(
        "-e",
        "--epsilon",
        required=False,
        type=float,
        default=1.0,
        help="Scale factor for initial state"
    )
    args = parser.parse_args()

    file_name = args.file

    if args.x0:
        initial_x = [float(v) for v in args.x0.split(",")]
    else:
        initial_x = [-0.01505422, -0.08406382,  0.17563262,  0.98074453]
        # initial_x = [5, 0, 0, 0]

    initial_x = [v * args.epsilon for v in initial_x]
    target_x = [0.0, 0.0, 0.0, 0.0]

    # lqr gains for mode 1 and mode 2
    # -23.770885 	-21.232774 	-88.144034 	-18.446548
    gains = {
        1: np.array([-0.866502, 	-1.688026, 	-18.727439, 	-3.592953]),
        2: np.array([-23.770885, 	-21.232774, 	-88.144034, 	-18.446548])
    }
    
    sim_results = run_event_simulation(
        file_name, A, B,
        gains,
        initial_x, 
        target_x
    )

    # max_deviation = sim_results['theta'].abs().idxmax()
    # print(sim_results.loc[max_deviation])
    results_file = file_name.split('.')[0] + '_states.csv'
    sim_results.to_csv(results_file, sep=',', index=False)

if __name__ == "__main__":
    main()