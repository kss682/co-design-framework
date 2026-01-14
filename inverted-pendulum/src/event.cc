#include "event.h"

Event::Event(event_type typ, double t, unsigned int id) : type(typ), time(t), packetid(id)
{
}
