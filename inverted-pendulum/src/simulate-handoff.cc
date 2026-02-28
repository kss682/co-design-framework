#include "inverted_pendulum.h"
#include "lqr.h"
#include <algorithm>
#include <boost/tokenizer.hpp>
#include <cmath>
#include <fstream>
#include <iostream>
#include <list>
#include <map>
#include <string.h>
#include <unistd.h>

// Physical parameters
#define PARAM_m  0.2
#define PARAM_M  0.5
#define PARAM_I  0.006
#define PARAM_l  0.3
#define PARAM_DT 0.0001

// LQR gains
// K_FAST: tuned for 5ms sampling (moving pendulum - tight control)
#define LQR_K_FAST {-0.96183101, -2.06165895, -23.80067011, -4.17745663}
// K_SLOW: tuned for 30ms sampling (stationary pendulum - relaxed control)
#define LQR_K_SLOW {-0.31661315, -0.71078538, -13.12746744, -2.35946295}

// Positions
#define P1_START  0.0   // P1 initial position
#define P1_HOLD   4.0   // P1 target / hold position after handoff
#define P2_HOLD   4.0   // P2 hold position before handoff
#define P2_TARGET 6.0   // P2 final target after handoff

#define INITIAL_STATE_P1 {P1_START, 0.0,  0.02, 0.0}
#define INITIAL_STATE_P2 {P2_HOLD,  0.0, -0.02, 0.0}

#define MAX_STR_LEN 1024

enum hier_event_type {
    evt_sensor_send,
    evt_lowctrl_receive,
    evt_actuator_receive,
    evt_state_to_high,
    evt_highctrl_receive,
    evt_setpoint_receive    // stream 13: HLC handoff GO command
};

struct HierEvent {
    hier_event_type  type;
    double           time;
    unsigned int     stream_id;
    unsigned int     packet_id;
    int              mode;
    unsigned int     plant_id;

    HierEvent(hier_event_type t, double tm, unsigned int sid,
              unsigned int pid, int m, unsigned int plant)
        : type(t), time(tm), stream_id(sid), packet_id(pid),
          mode(m), plant_id(plant) {}

    bool operator<(const HierEvent &o) const { return time < o.time; }
};

typedef std::list<HierEvent> event_queue_t;

event_queue_t event_queue;
char path_in_p1[MAX_STR_LEN];
char path_in_p2[MAX_STR_LEN];
char path_out[MAX_STR_LEN];

std::map<std::pair<unsigned int,unsigned int>, pendulum_state_t> pkt_to_state;
std::map<std::pair<unsigned int,unsigned int>, double>           pkt_to_control;

pendulum_state_t current_setpoint_p1 = {P1_HOLD, 0, 0, 0};
pendulum_state_t current_setpoint_p2 = {P2_HOLD, 0, 0, 0};

// --------------------------------------------------------------------------
int parse_cmdline_args(int argc, char *argv[])
{
    int opt;
    memset(path_in_p1, 0, MAX_STR_LEN);
    memset(path_in_p2, 0, MAX_STR_LEN);
    memset(path_out,   0, MAX_STR_LEN);

    while ((opt = getopt(argc, argv, "1:2:o:")) != -1) {
        switch (opt) {
        case '1': strncpy(path_in_p1, optarg, MAX_STR_LEN-1); break;
        case '2': strncpy(path_in_p2, optarg, MAX_STR_LEN-1); break;
        case 'o': strncpy(path_out,   optarg, MAX_STR_LEN-1); break;
        default:  return -1;
        }
    }
    if (!strlen(path_in_p1) || !strlen(path_in_p2) || !strlen(path_out))
        return -1;
    return 0;
}

void usage(const char *prog)
{
    std::cerr << "Usage: " << prog
              << " -1 <p1_trace> -2 <p2_trace> -o <output_csv>\n";
}

// --------------------------------------------------------------------------
hier_event_type parse_event_type(const std::string &token, unsigned int sid)
{
    // Sensor streams to LLC (low-level)
    if (token == "plantsend") {
        if (sid == 1 || sid == 4 || sid == 7 || sid == 10) return evt_sensor_send;
        if (sid == 2 || sid == 5 || sid == 8 || sid == 11) return evt_state_to_high;
    }
    if (token == "controllerreceive") {
        if (sid == 1 || sid == 4 || sid == 7 || sid == 10) return evt_lowctrl_receive;
        if (sid == 2 || sid == 5 || sid == 8 || sid == 11) return evt_highctrl_receive;
    }
    if (token == "plantreceive") {
        if (sid == 3 || sid == 6 || sid == 9 || sid == 12) return evt_actuator_receive;
        if (sid == 13)                                       return evt_setpoint_receive;
    }
    return evt_sensor_send;
}

// --------------------------------------------------------------------------
bool read_trace(const char *path, unsigned int default_plant_id)
{
    std::ifstream f(path);
    if (!f.is_open()) { perror("Cannot open trace"); return false; }

    std::string line;
    while (std::getline(f, line)) {
        if (line.empty() || line[0] == '#') continue;

        boost::char_separator<char> sep(",");
        boost::tokenizer<boost::char_separator<char>> tok(line, sep);
        std::vector<std::string> p;
        for (auto &t : tok) p.push_back(t);
        if (p.size() < 4) continue;

        double       time      = std::stod(p[0]);
        std::string  evt_str   = p[1];
        int          mode      = std::stoi(p[2]);
        unsigned int packet_id = std::stoul(p[3]);
        unsigned int stream_id = (p.size() >= 5) ? std::stoul(p[4]) : 0;
        unsigned int plant_id  = (p.size() >= 6) ? std::stoul(p[5]) : default_plant_id;

        hier_event_type etype = parse_event_type(evt_str, stream_id);
        event_queue.push_back(
            HierEvent(etype, time, stream_id, packet_id, mode, plant_id));
    }
    return true;
}

// --------------------------------------------------------------------------
pendulum_state_t gain_for(unsigned int stream_id)
{
    // Moving streams (fast, 5ms)
    if (stream_id == 1 || stream_id == 2 || stream_id == 3 ||
        stream_id == 7 || stream_id == 8 || stream_id == 9 || stream_id == 13)
        return LQR_K_FAST;
    // Stationary streams (slow, 30ms)
    return LQR_K_SLOW;
}

// --------------------------------------------------------------------------
bool print_csv(const char *path,
               const state_sequence_t &s1,
               const state_sequence_t &s2)
{
    std::ofstream o(path);
    if (!o.is_open()) { perror("Cannot open output"); return false; }

    // Format matches visualization_dual.cc:
    // t, x1, v1, phi1, omega1, x2, v2, phi2, omega2, distance, collision
    o << "# t,x1,v1,phi1,omega1,x2,v2,phi2,omega2,distance,collision\n";

    const double CART_WIDTH = 0.4; // collision threshold [m]

    auto it1 = s1.begin(), it2 = s2.begin();
    while (it1 != s1.end() && it2 != s2.end()) {
        double t1 = it1->first, t2 = it2->first;
        if (std::abs(t1-t2) < PARAM_DT/2.0) {
            double distance  = std::abs(it2->second[0] - it1->second[0]);
            int    collision  = (distance < CART_WIDTH) ? 1 : 0;
            o << t1 << ","
              << it1->second[0] << "," << it1->second[1] << ","
              << it1->second[2] << "," << it1->second[3] << ","
              << it2->second[0] << "," << it2->second[1] << ","
              << it2->second[2] << "," << it2->second[3] << ","
              << distance << "," << collision << "\n";
            ++it1; ++it2;
        } else if (t1 < t2) { ++it1; } else { ++it2; }
    }
    return true;
}

// --------------------------------------------------------------------------
int main(int argc, char *argv[])
{
    if (parse_cmdline_args(argc, argv) == -1) { usage(argv[0]); return 1; }

    if (!read_trace(path_in_p1, 1)) return 1;
    if (!read_trace(path_in_p2, 2)) return 1;

    event_queue.sort();

    pendulum_state_t init_p1 = INITIAL_STATE_P1;
    pendulum_state_t init_p2 = INITIAL_STATE_P2;

    InvertedPendulum p1(PARAM_m, PARAM_M, PARAM_I, PARAM_l, 0.0, init_p1);
    InvertedPendulum p2(PARAM_m, PARAM_M, PARAM_I, PARAM_l, 0.0, init_p2);

    state_sequence_t states_p1, states_p2;
    LQRegulator lqr(LQR_K_FAST);

    std::cout << "=== Coordinated Handoff Simulation ===\n";
    std::cout << "Mode 0: P1 moving (0->" << P1_HOLD
              << "), P2 stationary (" << P2_HOLD << ")\n";
    std::cout << "Mode 1: P1 stationary (" << P1_HOLD
              << "), P2 moving (" << P2_HOLD << "->" << P2_TARGET << ")\n";
    std::cout << "Events: " << event_queue.size() << "\n\n";

    bool handoff_done = false;
    int  current_mode = 0;

    while (!event_queue.empty()) {
        HierEvent e = event_queue.front();
        event_queue.pop_front();

        // Advance physics to event time
        double d1 = e.time - p1.get_time();
        double d2 = e.time - p2.get_time();
        if (d1 > 0) p1.simulate(d1, PARAM_DT, states_p1);
        if (d2 > 0) p2.simulate(d2, PARAM_DT, states_p2);

        // Detect mode transition — only advance, never retreat
        // (stale in-flight packets from the old mode arrive after the switch)
        if (e.mode > current_mode) {
            std::cout << "Mode switch at t=" << e.time
                      << ": " << current_mode << " -> " << e.mode << "\n";
            current_mode = e.mode;
        }

        InvertedPendulum    &pend    = (e.plant_id == 1) ? p1 : p2;
        pendulum_state_t    &setpt   = (e.plant_id == 1)
                                        ? current_setpoint_p1
                                        : current_setpoint_p2;
        auto pkt_key = std::make_pair(e.stream_id, e.packet_id);

        switch (e.type) {

        case evt_sensor_send:
            pkt_to_state[pkt_key] = pend.get_state();
            break;

        case evt_lowctrl_receive: {
            if (!pkt_to_state.count(pkt_key)) break;
            pendulum_state_t K = gain_for(e.stream_id);
            double u = lqr.control(pkt_to_state[pkt_key], setpt, K);
            pkt_to_control[pkt_key] = u;
            break;
        }

        case evt_actuator_receive: {
            // Stream 3 triggered by 1; stream 6 by 4; stream 9 by 7; stream 12 by 10
            unsigned int src_stream = e.stream_id - 1;  // triggered stream is src+1 in this layout?
            // Map triggered stream to its parent sensor stream
            unsigned int parent;
            switch (e.stream_id) {
                case  3: parent = 1; break;
                case  6: parent = 4; break;
                case  9: parent = 7; break;
                case 12: parent = 10; break;
                default: parent = e.stream_id - 1;
            }
            auto ctrl_key = std::make_pair(parent, e.packet_id);
            if (!pkt_to_control.count(ctrl_key)) break;
            pend.set_force(pkt_to_control[ctrl_key]);
            break;
        }

        case evt_setpoint_receive:
            // Stream 13: HLC handoff GO command arrives at P2 actuator
            // Update P2 setpoint to the moving target
            if (!handoff_done) {
                current_setpoint_p2 = {P2_TARGET, 0, 0, 0};
                handoff_done = true;
                std::cout << "  -> Handoff GO received at t=" << e.time
                          << " P2 setpoint: " << P2_HOLD
                          << " -> " << P2_TARGET << "\n";
            }
            break;

        case evt_state_to_high:
        case evt_highctrl_receive:
            // High-level events: no action needed in this simulator
            // The setpoint is updated only on stream 13 (evt_setpoint_receive)
            break;
        }
    }

    if (!print_csv(path_out, states_p1, states_p2)) return 1;

    std::cout << "\n=== Results ===\n";
    std::cout << "P1 final position: " << p1.get_state()[0]
              << " (target: " << P1_HOLD << ")\n";
    std::cout << "P2 final position: " << p2.get_state()[0]
              << " (target: " << P2_TARGET << ")\n";

    double err1 = std::abs(p1.get_state()[0] - P1_HOLD);
    double err2 = std::abs(p2.get_state()[0] - P2_TARGET);

    if (err1 < 0.1 && err2 < 0.1)
        std::cout << "SUCCESS: Both pendulums reached targets\n";
    else
        std::cout << "WARNING: Target not fully reached "
                  << "(P1 err=" << err1 << " P2 err=" << err2 << ")\n";

    return 0;
}
