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

// Mass of pendulum [kg]
#define PARAM_m 0.2
// Mass of cart [kg]
#define PARAM_M 0.5
// Moment of Inertia [kg*m^2]
#define PARAM_I 0.006
// Length of pendulum to center of mass [m]
#define PARAM_l 0.3
// Initial angle of pendulum [rad]
#define PARAM_angle 0.0
// Initial speed of cart [m/s]
#define PARAM_v 0.0
// Initial position of cart [m]
#define PARAM_x 5.0

// Duration of a simulation step [s]
#define PARAM_DT 0.0001

// LQR 
#define LQR_K_MODE1{-1.0000000000001679, -2.7126628569811633, 42.94618303488281, 5.411763498735041}
#define LQR_K_MODE0{ -1.0000000000001679, -2.7126628569811633, 42.94618303488281, 5.411763498735041}

// #define LQR_K_MODE1 {-6.769455, -6.308049, -32.345614, -6.270112}
// #define LQR_K_MODE0 {-0.730508, -1.631186, -21.128060, 	-4.365921}


#define MAX_STR_LEN 1024

#define TOKEN_PLANT_SEND "plantsend"
#define TOKEN_PLANT_RECEIVE "plantreceive"
#define TOKEN_CONTROLLER_RECEIVE "controllerreceive"

#define MODE_STATIONARY "stationary"
#define MODE_MOVING_1 "moving_1"
#define MODE_MOVING_2 "moving_2"

#define MODE_0 {5, 0, 0, 0}
#define MODE_1 {0, 0, 0, 0}
#define MODE_2 {5, 0, 0, 0}

char path_in[MAX_STR_LEN];
char path_out[MAX_STR_LEN];

typedef std::list<Event> event_queue_t;
event_queue_t event_queue;

std::map<unsigned int, pendulum_state_t> pkt_to_state;
std::map<unsigned int, double> pkt_to_update;
/**
 * Parse command line arguments as passed to main() and store them in
 * global variables.
 */
int parse_cmdline_args(int argc, char *argv[])
{
    int opt;

    memset(path_in, 0, MAX_STR_LEN);
    memset(path_out, 0, MAX_STR_LEN);

    while ((opt = getopt(argc, argv, "f:o:")) != -1)
    {
        switch (opt)
        {
        case 'f':
            strncpy(path_in, optarg, MAX_STR_LEN - 1);
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

    if ((strlen(path_in) == 0) || (strlen(path_out) == 0))
        return -1;

    return 0;
}

void usage(const char *prog)
{
    std::cerr << "Usage:" << prog << std::endl;
    std::cerr << "-f: PACKET_TRACE_INPUT_FILE" << std::endl;
    std::cerr << "-o: PENDULUM_STATE_OUTPUT_FILE" << std::endl;
}

bool print_states_csv(const char *path, const state_sequence_t &states)
{
    std::ofstream ofile(path);

    if (!ofile.is_open())
    {
        perror("Could not open output file");
        return false;
    }
    ofile << "# t,x,v,phi,omega" << std::endl;
    for (const time_state_t &ts : states)
    {
        ofile << ts.first << "," << ts.second[0] << "," << ts.second[1] << "," << ts.second[2] << "," << ts.second[3]
              << std::endl;
    }

    return true;
}

bool read_trace(const char *path, event_queue_t &event_queue)
{
    std::ifstream infile(path);

    if (!infile.is_open())
    {
        perror("Could not open trace file");
        return -1;
    }

    std::string line;
    while (std::getline(infile, line))
    {
        // Ignore empty lines with no characters
        if (line.empty())
            continue;
        // Ignore lines starting with #
        if (line.rfind("#", 0) == 0)
            continue;
        boost::char_separator<char> sep(",");
        boost::tokenizer<boost::char_separator<char>> tokens(line, sep);
        unsigned int token_cnt = 0;
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
                mode = static_cast<mode_type> (std::stoi(token.c_str()));
                break;
            case 3:
                packetid = strtol(token.c_str(), NULL, 10);
                break;
            default:
                std::cerr << "Too many tokens in line: " << line << std::endl;
                return false;
            }
            column++;
            token_cnt++;
        }

        if (token_cnt < 3)
        {
            std::cerr << "Too few tokens" << std::endl;
            return false;
        }

        event_queue.push_back(Event(type, t, packetid, mode));
    }

    return true;
}

int main(int argc, char *argv[])
{
    if (parse_cmdline_args(argc, argv) == -1)
    {
        usage(argv[0]);
        exit(1);
    }

    if (!read_trace(path_in, event_queue))
    {
        exit(1);
    }

    /*
     * Initial pendulum state vector:
     *
     * [  x  ]
     * [  v  ]
     * [ phi ]
     * [omega]
     */
    pendulum_state_t state_initial = MODE_0;
    InvertedPendulum pendulum = InvertedPendulum(PARAM_m, PARAM_M, PARAM_I, PARAM_l, 0.0, state_initial);
    state_sequence_t states;

    LQRegulator lqr(LQR_K_MODE1);

    pendulum_state_t current_target;
    while (!event_queue.empty())
    {
        Event e = *event_queue.begin();
        event_queue.pop_front();

        // Execute simulation until time of next event.
        double dsim = e.time - pendulum.get_time();
        if (dsim > 0.0)
            pendulum.simulate(dsim, PARAM_DT, states);

        // Execute event.
        pendulum_state_t state;
        double u;
        switch (e.type)
        {
        case event_plant_send:
            pkt_to_state[e.packetid] = pendulum.get_state();
            break;
        case event_controller_receive:
            if (pkt_to_state.find(e.packetid) == pkt_to_state.end())
            {
                std::cout << e.packetid << " " << e.type << std::endl;
                std::cerr << "Missing state" << std::endl;
                // exit(1);
            }
            state = pkt_to_state[e.packetid];
            u = lqr.control(state);
            // if(e.mode == stationary) u = lqr.control(state, MODE_0, LQR_K_MODE0);
            // else if(e.mode == moving_1) u = lqr.control(state, MODE_1, LQR_K_MODE1);
            // else if(e.mode == moving_2) u = lqr.control(state, MODE_2, LQR_K_MODE1);
            
            pkt_to_update[e.packetid] = u;


            // exit(1);
            break;
        case event_plant_receive:
            if (pkt_to_update.find(e.packetid) == pkt_to_update.end())
            {
                std::cerr << "Missing update for packet id " << e.packetid << std::endl;
                // exit(1);
            }
            u = pkt_to_update[e.packetid];
            std::cout << "time: " << e.time << std::endl;
            std::cout << "control: " << u << std::endl;
            pendulum.set_force(u);
            break;
        }
    }

    if (!print_states_csv(path_out, states))
    {
        std::cerr << "Could not write states to file" << std::endl;
        exit(1);
    }

    return 0;
}
