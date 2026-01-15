#include "event.h"

Event::Event(event_type typ, double t, unsigned int id, mode_type mode) 
    : type(typ), time(t), packetid(id), mode(mode){}
