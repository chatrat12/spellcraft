#ifndef __SPELL_SPELL_EVENT_H__
#define __SPELL_SPELL_EVENT_H__

#include <stdint.h>
#include "spell_data_source.h"

#define MAX_EVENT_COUNT 4

enum spell_event_type {
    SPELL_EVENT_PRIMARY,
    SPELL_EVENT_SECONDARY,
    SPELL_EVENT_DESTROY,
};

struct spell_event {
    uint8_t type;
    struct spell_data_source* data_source;
};

struct spell_event_listener {
    struct spell_event events[MAX_EVENT_COUNT];
    uint8_t event_count;
};


void spell_event_listener_init(struct spell_event_listener* listener);
void spell_event_listener_add(struct spell_event_listener* listener, enum spell_event_type type, struct spell_data_source* data_source);
void spell_event_listener_destroy(struct spell_event_listener* listener);

#endif