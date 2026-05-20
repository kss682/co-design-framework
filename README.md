# Co-Design Validation Framework for Networked Control Systems

A Timed Colored Petri Net (TCPN) based framework for validating the co-design of control and network in Networked Control Systems (NCS). The framework models time-triggered data flows, simulates mode switching strategies, and validates delivery guarantees during mode transitions.


## Overview

In NCS, sensors, controllers, and actuators communicate over a shared network. When the system transitions between modes of operation (e.g., changing the sampling rate and controller gains), both the control parameters and the network schedule must be reconfigured. During this transition window, system safety is not guaranteed.

The framework enables co-design by allowing the designer to jointly evaluate and iterate on:
- **Control parameters**: controller gain (K), sampling period (h), and the resulting stability tolerance (S_app)
- **Network schedule**: delivery pattern, consecutive miss guarantees (S_net), and reconfiguration delay (delta)
- **Mode design**: number of modes, transition direction, and switch timing

By simulating the Petri Net model with different configurations, the designer can verify whether the sufficient condition for safety is satisfied during mode transitions, and identify which parameters (control tuning, network schedule, or reconfiguration delay) need adjustment when it is not.

This framework:
1. Models the NCS as a Timed-Colored Petri Net with configurable network schedules
2. Simulates mode transitions under different switching strategies (synchronized and delayed)
3. Validates a sufficient condition for system safety based on weakly-hard real-time (WHRT) guarantees
4. Produces packet delivery traces for closed-loop plant simulation

## Project Structure

```
.
├── main.py                  # Entry point: loads config, builds Petri Net, runs simulation
├── pendulum_simulator.py    # Event-driven pendulum simulator (ZOH + scipy RK45)
├── lqr.ipynb                # LQR gain computation and spectral analysis
├── confidence_plot.ipynb    # Evaluation plots for thesis
├── run_single_mode_stability.sh  # Evaluation: single-mode stability analysis (pattern sweep)
├── run_delta_sweep.sh            # Evaluation: mode switch delta sweep
├── run_switch_time_sweep.sh      # Evaluation: switch time analysis
├── models/                  # Data models
│   ├── node.py              # Network node (end system / network node)
│   ├── links.py             # Directed link between nodes
│   ├── stream.py            # Traffic stream, packet, timer
│   ├── mode.py              # Mode of operation
│   ├── place.py             # Petri Net places (stream and network)
│   └── constants.py         # Place type constants
├── switch_module/           # Mode switching strategies
│   ├── base.py              # Abstract base class for switching
│   ├── synchronized_switch.py  # Synchronised switch (hypercycle-aligned)
│   └── delayed_switch.py    # Delayed switch (application-first with delta)
├── reporter/                # Simulation reporting and validation
│   ├── time_reporter.py     # End-to-end latency, deadline validation, transition window
│   └── delivery_constraints.py  # Packet delivery constraint definitions
├── simpn/                   # Vendored SimPN Petri Net engine (modified, see simpn/NOTICE)
├── json/                    # Network configuration files
│   └── single_pendulum_cart_1/
│       └── network.json     # Example: single pendulum with two modes
└── benchmark/               # Evaluation results (delta sweeps, pattern sweeps)
```

## Installation

```bash
git clone git@github.com:kss682/co-design-framework.git
cd co-design-framework
pip install -r requirements.txt
```

Requires Python 3.10+.

## Usage

### Single Simulation Run

```bash
python main.py -f json/single_pendulum_cart_1/network.json -s Delay -t 20 -d 0.03
```

| Flag | Description |
|------|-------------|
| `-f` | Path to JSON network configuration file |
| `-s` | Switch strategy: `Sync` (synchronised) or `Delay` (delayed/application-first) |
| `-t` | Simulation time (seconds) |
| `-d` | Reconfiguration delay delta (seconds), used with `Delay` strategy |
| `-sw` | Override mode switch time (seconds) |
| `-b N` | Benchmark mode: run N iterations for stochastic guarantees |

### Single-Mode Stability Analysis

```bash
./run_single_mode_stability.sh
```

Sweeps over consecutive miss patterns (0 to 10 misses) for a single mode, validates the WHRT bound against the plant simulator.
The JSON is inside the script, the system being evaluated has to be placed inside the script. 

### Delta Sweep (Mode Switch Evaluation)

```bash
./run_delta_sweep.sh json/single_pendulum_cart_1/network.json
```

Iterates delta from 10ms to 250ms, runs the Petri Net simulation and pendulum simulator for each value, and writes results to `benchmark/`.

### Switch Time Sweep

```bash
./run_switch_time_sweep.sh json/single_pendulum_cart_1/network.json
```

Sweeps over switch timing (hit index 1-10) and delta values to analyze the effect of deferring the mode switch.

### Inverted Pendulum Simulator

After running the Petri Net simulation, feed the generated trace to the pendulum simulator:

```bash
python pendulum_simulator.py -f simulation_results/plant1_trace.csv
```

## JSON Configuration

The network model is defined in a JSON file with the following structure:

| Key | Description |
|-----|-------------|
| `nodes` | List of nodes with `id` and `type` (`ES` = end system, `NN` = network node) |
| `links` | Directed links between nodes (`src` -> `dst`) |
| `streams` | Traffic streams with `period`, `deadline`, and optional `triggered_by` for event-triggered streams |
| `modes` | Modes of operation mapping to active streams and schedule |
| `schedules` | Per-mode delivery pattern (e.g., `[1, 0, 0]` = hit, miss, miss) with hit/miss delays |
| `mode_switch` | Sequence of `[mode_id, switch_time]` pairs |
| `delivery_constraints` | WHRT constraints: `min_packets` = max consecutive misses tolerated (S_app) |
| `link_delay` | Probabilistic link delay model |

## Key Concepts

- **Mode of Operation**: A configuration defined by the controller parameters (gain K, sampling period h) and the corresponding network schedule
- **S_app**: Maximum consecutive deadline misses the closed-loop system can tolerate while remaining stable, derived from spectral radius analysis
- **Sufficient Condition**: The transition window T_worst must satisfy T_worst <= min(S_app_i * h_i, S_app_j * h_j) for safety during mode switch
- **Switching Strategies**:
  - *Synchronized*: Both control and network switch at the next hypercycle boundary
  - *Delayed*: Control switches first; network reconfigures after delay delta

## License

This project is licensed under the GPL-3.0 License. See [LICENSE](LICENSE) for details.

The `simpn/` directory contains a modified version of [SimPN](https://github.com/bpogroup/simpn) (MIT License). See [simpn/NOTICE](simpn/NOTICE).
