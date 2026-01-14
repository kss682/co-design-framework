#include <fstream>
#include <iostream>
#include <list>
#include <map>
#include <string.h>
#include <unistd.h>

#include "event.h"

#define MAX_STR_LEN 1024

#define TOKEN_PLANT_SEND "plantsend"
#define TOKEN_PLANT_RECEIVE "plantreceive"
#define TOKEN_CONTROLLER_RECEIVE "controllerreceive"

char path_plantsend[MAX_STR_LEN];
char path_plantreceive[MAX_STR_LEN];
char path_controllerreceive[MAX_STR_LEN];
char path_out[MAX_STR_LEN];

typedef std::list<Event> event_queue_t;
event_queue_t event_queue;

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
        perror("Could not open trace file");
        return -1;
    }

    unsigned int packetid = 0;
    std::string line;
    while (std::getline(infile, line))
    {
        // Ignore empty lines with no characters
        if (line.empty())
            continue;

        double d = strtod(line.c_str(), NULL);
        Event e(type, d, packetid);
        event_queue.push_back(e);
        packetid++;
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
    ofile << "# t,event_type,packet_id" << std::endl;
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
