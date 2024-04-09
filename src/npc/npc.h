#ifndef __NPC_NPC_H__
#define __NPC_NPC_H__

#include "../scene/world_definition.h"
#include "../math/transform_single_axis.h"
#include "../render/renderable.h"
#include "../render/animator.h"
#include "../collision/dynamic_object.h"

struct npc_information {
    char* mesh;
    char* animations;
    struct dynamic_object_type collider;
    float half_height;
};

struct npc_animations {
    struct animation_clip* idle;
};

struct npc {
    struct TransformSingleAxis transform;
    struct renderable_single_axis renderable;

    struct dynamic_object collider;

    struct animation_set* animation_set;
    struct npc_animations animations;
    struct animator animator;
};

void npc_init(struct npc* npc, struct npc_definition* definiton);
void npc_destroy(struct npc* npc);

#endif