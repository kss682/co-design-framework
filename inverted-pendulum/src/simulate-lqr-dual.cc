#include "event.h"
#include "inverted_pendulum.h"
#include "lqr.h"
#include <boost/tokenizer.hpp>
#include <fstream>
#include <iostream>
#include <list>
#include <map>
#include <string.h>
#include <unistd.h>
#include <algorithm>
#include <utility>

// Mass of pendulum [kg]
#define PARAM_m 0.2
// Mass of cart [kg]
#define PARAM_M 0.5
// Moment of Inertia [kg*m^2]
#define PARAM_I 0.006
// Length of pendulum to center of mass [m]
#define PARAM_l 0.3

// Duration of a simulation step [s]
#define PARAM_DT 0.0001

// LQR gain matrices for different modes
#define LQR_K_MODE1 {-0.96183101,  -2.06165895, -23.80067011,  -4.17745663}
#define LQR_K_MODE0 {-0.31661315,  -0.71078538, -13.12746744,  -2.35946295}

#define MAX_STR_LEN 1024

#define TOKEN_PLANT_SEND "plantsend"
#define TOKEN_PLANT_RECEIVE "plantreceive"
#define TOKEN_CONTROLLER_RECEIVE "controllerreceive"

// Formation targets for each mode
// Mode 0 (left_formation): P1 at x=1, P2 at x=3
#define MODE_0_P1 {1.0, 0, 0, 0}
#define MODE_0_P2 {3.0, 0, 0, 0}
// Mode 1 (right_formation): P1 at x=5, P2 at x=7
#define MODE_1_P1 {5.0, 0, 0, 0}
#define MODE_1_P2 {7.0, 0, 0, 0}

// Initial states
#define INITIAL_STATE_P1 {1.0, 0, 0, 0}
#define INITIAL_STATE_P2 {3.0, 0, 0, 0}

// Minimum safe distance between pendulums
#define MIN_SAFE_DISTANCE 1.5

char path_in_p1[MAX_STR_LEN];
char path_in_p2[MAX_STR_LEN];
char path_out[MAX_STR_LEN];

// Extended event with plant ID
struct DualEvent {
    event_type type;
    double time;
    unsigned int packetid;
    mode_type mode;
    unsigned int plant_id;  // 1 or 2

    DualEvent(event_type t, double tm, unsigned int pid, mode_type m, unsigned int plant)
        : type(t), time(tm), packetid(pid), mode(m), plant_id(plant) {}

    bool operator<(const DualEvent &other) const {
        return time < other.time;
    }
};

typedef std::list<DualEvent> event_queue_t;
event_queue_t event_queue;

// Per-plant packet tracking: (plant_id, packet_id) -> state/update
std::map<std::pair<unsigned int, unsigned int>, pendulum_state_t> pkt_to_state;
std::map<std::pair<unsigned int, unsigned int>, double> pkt_to_update;

// Collision tracking
bool collision_detected = false;
double collision_time = -1.0;

int parse_cmdline_args(int argc, char *argv[])
{
    int opt;

    memset(path_in_p1, 0, MAX_STR_LEN);
    memset(path_in_p2, 0, MAX_STR_LEN);
    memset(path_out, 0, MAX_STR_LEN);

    while ((opt = getopt(argc, argv, "1:2:o:")) != -1)
    {
        switch (opt)
        {
        case '1':
            strncpy(path_in_p1, optarg, MAX_STR_LEN - 1);
            break;
        case '2':
            strncpy(path_in_p2, optarg, MAX_STR_LEN - 1);
            break;
        case 'o':
            strncpy(path_out, optarg, MAX_STR_LEN - 1);
            break;
        case ':':
        case '?':
        default:
            return -1;
        }
    }

    if ((strlen(path_in_p1) == 0) || (strlen(path_in_p2) == 0) || (strlen(path_out) == 0))
        return -1;

    return 0;
}

void usage(const char *prog)
{
    std::cerr << "Usage: " << prog << std::endl;
    std::cerr << "-1: PACKET_TRACE_INPUT_FILE_PLANT1" << std::endl;
    std::cerr << "-2: PACKET_TRACE_INPUT_FILE_PLANT2" << std::endl;
    std::cerr << "-o: PENDULUM_STATE_OUTPUT_FILE" << std::endl;
}

bool print_states_csv(const char *path, const state_sequence_t &states_p1, const state_sequence_t &states_p2)
{
    std::ofstream ofile(path);

    if (!ofile.is_open())
    {
        perror("Could not open output file");
        return false;
    }

    ofile << "# t,x1,v1,phi1,omega1,x2,v2,phi2,omega2,distance,collision" << std::endl;

    // Merge states from both pendulums by time
    auto it1 = states_p1.begin();
    auto it2 = states_p2.begin();

    while (it1 != states_p1.end() && it2 != states_p2.end())
    {
        double t1 = it1->first;
        double t2 = it2->first;

        if (std::abs(t1 - t2) < PARAM_DT / 2.0)
        {
            // Times match - output combined state
            double distance = std::abs(it2->second[0] - it1->second[0]);
            int collision = (distance < MIN_SAFE_DISTANCE) ? 1 : 0;

            ofile << t1 << ","
                  << it1->second[0] << "," << it1->second[1] << ","
                  << it1->second[2] << "," << it1->second[3] << ","
                  << it2->second[0] << "," << it2->second[1] << ","
                  << it2->second[2] << "," << it2->second[3] << ","
                  << distance << "," << collision << std::endl;
            ++it1;
            ++it2;
        }
        else if (t1 < t2)
        {
            ++it1;
        }
        else
        {
            ++it2;
        }
    }

    return true;
}

bool read_trace(const char *path, event_queue_t &event_queue, unsigned int plant_id)
{
    std::ifstream infile(path);

    if (!infile.is_open())
    {
        perror("Could not open trace file");
        return false;
    }

    std::string line;
    while (std::getline(infile, line))
    {
        if (line.empty())
            continue;
        if (line.rfind("#", 0) == 0)
            continue;

        boost::char_separator<char> sep(",");
        boost::tokenizer<boost::char_separator<char>> tokens(line, sep);
        unsigned int column = 0;
        double t;
        unsigned int packetid;
        event_type type;
        mode_type mode;

        for (const auto &token : tokens)
        {
            switch (column)
            {
            case 0:
                t = strtod(token.c_str(), NULL);
                break;
            case 1:
                if (token.compare(TOKEN_PLANT_SEND) == 0)
                {
                    type = event_plant_send;
                }
                else if (token.compare(TOKEN_PLANT_RECEIVE) == 0)
                {
                    type = event_plant_receive;
                }
                else if (token.compare(TOKEN_CONTROLLER_RECEIVE) == 0)
                {
                    type = event_controller_receive;
                }
                else
                {
                    std::cerr << "Unknown event type: " << token << std::endl;
                    return false;
                }
                break;
            case 2:
                mode = static_cast<mode_type>(std::stoi(token.c_str()));
                break;
            case 3:
                packetid = strtol(token.c_str(), NULL, 10);
                break;
            default:
                break;
            }
            column++;
        }

        if (column < 4)
        {
            std::cerr << "Too few tokens in line: " << line << std::endl;
            return false;
        }

        event_queue.push_back(DualEvent(type, t, packetid, mode, plant_id));
    }

    return true;
}

void check_collision(const InvertedPendulum &p1, const InvertedPendulum &p2, double current_time)
{
    double x1 = p1.get_state()[0];
    double x2 = p2.get_state()[0];
    double distance = std::abs(x2 - x1);

    if (distance < MIN_SAFE_DISTANCE && !collision_detected)
    {
        collision_detected = true;
        collision_time = current_time;
        std::cerr << "COLLISION DETECTED at t=" << current_time
                  << " (x1=" << x1 << ", x2=" << x2
                  << ", distance=" << distance << ")" << std::endl;
    }
}

int main(int argc, char *argv[])
{
    if (parse_cmdline_args(argc, argv) == -1)
    {
        usage(argv[0]);
        exit(1);
    }

    // Read traces for both plants
    if (!read_trace(path_in_p1, event_queue, 1))
    {
        std::cerr << "Failed to read trace for plant 1" << std::endl;
        exit(1);
    }

    if (!read_trace(path_in_p2, event_queue, 2))
    {
        std::cerr << "Failed to read trace for plant 2" << std::endl;
        exit(1);
    }

    // Sort events by time
    event_queue.sort();

    // Initialize both pendulums
    pendulum_state_t state_initial_p1 = INITIAL_STATE_P1;
    pendulum_state_t state_initial_p2 = INITIAL_STATE_P2;

    InvertedPendulum pendulum1 = InvertedPendulum(PARAM_m, PARAM_M, PARAM_I, PARAM_l, 0.0, state_initial_p1);
    InvertedPendulum pendulum2 = InvertedPendulum(PARAM_m, PARAM_M, PARAM_I, PARAM_l, 0.0, state_initial_p2);

    state_sequence_t states_p1;
    state_sequence_t states_p2;

    LQRegulator lqr(LQR_K_MODE0);

    while (!event_queue.empty())
    {
        DualEvent e = *event_queue.begin();
        event_queue.pop_front();

        // Simulate both pendulums until time of next event
        double dsim1 = e.time - pendulum1.get_time();
        double dsim2 = e.time - pendulum2.get_time();

        if (dsim1 > 0.0)
            pendulum1.simulate(dsim1, PARAM_DT, states_p1);
        if (dsim2 > 0.0)
            pendulum2.simulate(dsim2, PARAM_DT, states_p2);

        // Check for collision after simulation
        check_collision(pendulum1, pendulum2, e.time);

        // Get references based on plant_id
        InvertedPendulum &pendulum = (e.plant_id == 1) ? pendulum1 : pendulum2;
        auto pkt_key = std::make_pair(e.plant_id, e.packetid);

        // Execute event
        pendulum_state_t state;
        double u;

        switch (e.type)
        {
        case event_plant_send:
            pkt_to_state[pkt_key] = pendulum.get_state();
            break;

        case event_controller_receive:
            if (pkt_to_state.find(pkt_key) == pkt_to_state.end())
            {
                std::cerr << "Missing state for plant " << e.plant_id
                          << " packet " << e.packetid << std::endl;
            }
            state = pkt_to_state[pkt_key];

            // Select target and gain based on mode and plant
            if (e.mode == stationary)
            {
                pendulum_state_t target = (e.plant_id == 1) ?
                    pendulum_state_t(MODE_0_P1) : pendulum_state_t(MODE_0_P2);
                u = lqr.control(state, target, LQR_K_MODE0);
            }
            else if (e.mode == moving_1)
            {
                pendulum_state_t target = (e.plant_id == 1) ?
                    pendulum_state_t(MODE_1_P1) : pendulum_state_t(MODE_1_P2);
                u = lqr.control(state, target, LQR_K_MODE1);
            }
            else if (e.mode == moving_2)
            {
                pendulum_state_t target = (e.plant_id == 1) ?
                    pendulum_state_t(MODE_0_P1) : pendulum_state_t(MODE_0_P2);
                u = lqr.control(state, target, LQR_K_MODE1);
            }

            pkt_to_update[pkt_key] = u;
            break;

        case event_plant_receive:
            if (pkt_to_update.find(pkt_key) == pkt_to_update.end())
            {
                std::cerr << "Missing update for plant " << e.plant_id
                          << " packet " << e.packetid << std::endl;
            }
            u = pkt_to_update[pkt_key];
            pendulum.set_force(u);
            break;
        }
    }

    // Write combined output
    if (!print_states_csv(path_out, states_p1, states_p2))
    {
        std::cerr << "Could not write states to file" << std::endl;
        exit(1);
    }

    
    std::cout << "Simulation complete." << std::endl;
    std::cout << "Plant 1 states: " << states_p1.size() << std::endl;
    std::cout << "Plant 2 states: " << states_p2.size() << std::endl;

    if (collision_detected)
    {
        std::cout << "COLLISION occurred at t=" << collision_time << std::endl;
        return 1;  // Non-zero exit code indicates collision
    }
    else
    {
        std::cout << "No collision detected - formation maintained." << std::endl;
        return 0;
    }
}
