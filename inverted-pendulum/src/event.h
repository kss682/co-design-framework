#ifndef EVENT_H
#define EVENT_H

enum event_type
{
    event_plant_send,
    event_plant_receive,
    event_controller_receive
};

enum mode_type
{
    stationary,
    moving,
};

class Event
{
  public:
    event_type type;
    double time;
    unsigned int packetid;
    mode_type mode;

    Event(event_type type, double t, unsigned int packetid, mode_type mode);
};

#endif
