#include <fstream>
#include <iostream>
#include <list>
#include <map>
#include <sstream>
#include <string.h>
#include <unistd.h>
#include "event.h"

#define MAX_STR_LEN 1024

#define TOKEN_PLANT_SEND "plantsend"
#define TOKEN_PLANT_RECEIVE "plantreceive"
#define TOKEN_CONTROLLER_RECEIVE "controllerreceive"

#define MODE_STATIONARY "stationary"
#define MODE_MOVING_1 "moving_1"
#define MODE_MOVING_2 "moving_2"

char path_plantsend[MAX_STR_LEN];
char path_plantreceive[MAX_STR_LEN];
char path_controllerreceive[MAX_STR_LEN];
char path_out[MAX_STR_LEN];

typedef std::list<Event> event_queue_t;
event_queue_t event_queue;

std::vector<std::string> split(std::string& line, char delimiter){
    std::vector<std::string> fields;
    std::string token;

    std::stringstream ss(line);
    while (std::getline(ss, token, delimiter)) {
        fields.push_back(token);
    }
    return fields;

}

int parse_cmdline_args(int argc, char *argv[])
{
    int opt;

    memset(path_plantsend, 0, MAX_STR_LEN);
    memset(path_plantreceive, 0, MAX_STR_LEN);
    memset(path_controllerreceive, 0, MAX_STR_LEN);
    memset(path_out, 0, MAX_STR_LEN);

    while ((opt = getopt(argc, argv, "a:b:c:o:")) != -1)
    {
        switch (opt)
        {
        case 'a':
            strncpy(path_plantsend, optarg, MAX_STR_LEN - 1);
            break;
        case 'b':
            strncpy(path_plantreceive, optarg, MAX_STR_LEN - 1);
            break;
        case 'c':
            strncpy(path_controllerreceive, optarg, MAX_STR_LEN - 1);
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

    if ((strlen(path_plantsend) == 0) || (strlen(path_plantreceive) == 0) || (strlen(path_controllerreceive) == 0) ||
        (strlen(path_out) == 0))
        return -1;

    return 0;
}

bool read_trace(const char *path, event_queue_t &event_queue, event_type type)
{
    std::ifstream infile(path);

    if (!infile.is_open())
    {
        std::cout << path << std::endl;
        perror("Could not open trace file");
        return -1;
    }

    unsigned int packetid;
    std::string line;
    while (std::getline(infile, line))
    {
        // Ignore empty lines with no characters
        if (line.empty())
            continue;
        
        std::vector<std::string> fields = split(line, ',');
        if(fields.size() > 3){
            std::cerr << "Wrong format in input csv " << path << std::endl;
        }
        
        // std::cout << fields[0] << " " << fields[1] << std::endl;
        int mode = std::stoi(fields[0].c_str());
        double d = strtod(fields[1].c_str(), NULL);
        packetid = std::stoi(fields[2].c_str());
        Event e(type, d, packetid, static_cast<mode_type>(mode));
        event_queue.push_back(e);
    }

    return true;
}

bool print_trace_csv(const char *path, const event_queue_t &event_queue)
{
    std::ofstream ofile(path);

    if (!ofile.is_open())
    {
        perror("Could not open output file");
        return false;
    }
    ofile << "# t,event_type,mode_type,packet_id" << std::endl;
    for (const Event &e : event_queue)
    {
        ofile << e.time << ",";
        switch (e.type)
        {
        case event_plant_send:
            ofile << TOKEN_PLANT_SEND << ",";
            break;
        case event_plant_receive:
            ofile << TOKEN_PLANT_RECEIVE << ",";
            break;
        case event_controller_receive:
            ofile << TOKEN_CONTROLLER_RECEIVE << ",";
            break;
        }
        ofile << e.mode << ",";
        // switch (e.mode){
        //     case stationary:
        //         ofile << MODE_STATIONARY << ",";
        //         break;
        //     case moving_1:
        //         ofile << MODE_MOVING_1 << ",";
        //         break;
        //     case moving_2:
        //         ofile << MODE_MOVING_2 << ",";
        //         break;
        // }
        ofile << e.packetid << std::endl;
    }

    return true;
}

void usage(const char *prog)
{
    std::cerr << "Usage:" << prog << std::endl;
    std::cerr << "-a: TRACE_FILE_PLANT_SEND" << std::endl;
    std::cerr << "-b: TRACE_FILE_PLANT_RECEIVE" << std::endl;
    std::cerr << "-c: TRACE_FILE_CONTROLLER_RECEIVE" << std::endl;
    std::cerr << "-o: MERGED_TRACE_FILE" << std::endl;
}

bool compare_event_time(const Event &e1, const Event &e2)
{
    if (e1.time <= e2.time)
        return true;
    else
        return false;
}

int main(int argc, char *argv[])
{
    if (parse_cmdline_args(argc, argv) == -1)
    {
        usage(argv[0]);
        exit(1);
    }

    if (!read_trace(path_plantsend, event_queue, event_plant_send))
    {
        exit(1);
    }

    if (!read_trace(path_plantreceive, event_queue, event_plant_receive))
    {
        exit(1);
    }

    if (!read_trace(path_controllerreceive, event_queue, event_controller_receive))
    {
        exit(1);
    }

    event_queue.sort(compare_event_time);

    if (!print_trace_csv(path_out, event_queue))
    {
        std::cerr << "Could not write CSV file." << std::endl;
        exit(1);
    }
}
