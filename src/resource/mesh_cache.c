#include "mesh_cache.h"

#include <libdragon.h>
#include <GL/gl.h>

#include "resource_cache.h"
#include "../math/vector3.h"
#include "../math/vector2.h"
#include "../render/coloru8.h"
#include "material_cache.h"

// MESH
#define EXPECTED_HEADER 0x4D455348

bool mesh_load(struct mesh* into, const char* path) {
    FILE* meshFile = asset_fopen(path, NULL);

    int header;
    fread(&header, 1, 4, meshFile);
    assert(header == EXPECTED_HEADER);

    uint8_t submesh_count;
    fread(&submesh_count, 1, 1, meshFile);
    mesh_init(into, submesh_count);

    for (uint16_t i = 0; i < submesh_count; ++i) {

        uint8_t strLength;

        fread(&strLength, 1, 1, meshFile);

        if (strLength) {
            char materialName[strLength + 1];
            fread(materialName, 1, strLength, meshFile);
            materialName[strLength] = '\0';
            into->materials[i] = material_cache_load(materialName);
        }

        uint8_t attributes;
        fread(&attributes, 1, 1, meshFile);

        assert(attributes <= MeshAttributesAll);

        GLuint vertexBuffer;
        GLuint vertexArray;
        glGenVertexArrays(1, &vertexArray);
        glBindVertexArray(vertexArray);
        glGenBuffersARB(1, &vertexBuffer);
        glBindBufferARB(GL_ARRAY_BUFFER_ARB, vertexBuffer);

        int offset = 0;
        int size = mesh_attribute_size(attributes);

        if (attributes & MeshAttributesPosition) {
            glEnableClientState(GL_VERTEX_ARRAY);
            glVertexPointer(3, GL_HALF_FIXED_N64, size, (void*)offset);

            offset += sizeof(short) * 3;
        }

        if (attributes & MeshAttributesUV) {
            glEnableClientState(GL_TEXTURE_COORD_ARRAY);
            glTexCoordPointer(2, GL_HALF_FIXED_N64, size, (void*)offset);

            offset += sizeof(short) * 2;
        }

        if (attributes & MeshAttributesColor) {
            glEnableClientState(GL_COLOR_ARRAY);
            glColorPointer(4, GL_BYTE, size, (void*)offset);

            offset += sizeof(struct Coloru8);
        }

        if (attributes & MeshAttributesNormal) {
            glEnableClientState(GL_NORMAL_ARRAY);
            glNormalPointer(GL_BYTE, size, (void*)offset);

            offset += sizeof(char) * 3;
        }

        uint16_t vertexCount;
        fread(&vertexCount, 2, 1, meshFile);

        glBufferDataARB(GL_ARRAY_BUFFER_ARB, vertexCount * size, NULL, GL_STATIC_DRAW_ARB);
        void* vertices = glMapBufferARB(GL_ARRAY_BUFFER_ARB, GL_WRITE_ONLY_ARB);
        fread(vertices, size, vertexCount, meshFile);
        glUnmapBufferARB(GL_ARRAY_BUFFER_ARB);

        int indexSize = vertexCount >= 256 ? 2 : 1;

        uint16_t indexCount;
        fread(&indexCount, 2, 1, meshFile);

        GLuint indexBuffer;
        glGenBuffersARB(1, &indexBuffer);
        glBindBufferARB(GL_ARRAY_BUFFER_ARB, indexBuffer);
        
        glBufferDataARB(GL_ARRAY_BUFFER_ARB, indexCount * indexSize, NULL, GL_STATIC_DRAW_ARB);
        void* indices = glMapBufferARB(GL_ARRAY_BUFFER_ARB, GL_WRITE_ONLY_ARB);
        fread(indices, indexSize, indexBuffer, meshFile);
        glUnmapBufferARB(GL_ARRAY_BUFFER_ARB);

        glBindVertexArray(0);
        glBindBufferARB(GL_ARRAY_BUFFER_ARB, 0);

        glNewList(into->list + i, GL_COMPILE);
        glBindBufferARB(GL_ELEMENT_ARRAY_BUFFER_ARB, indexBuffer);
        glBindVertexArray(vertexArray);
        glDrawElements(GL_TRIANGLES, indexCount, indexSize == 1 ? GL_UNSIGNED_BYTE : GL_UNSIGNED_SHORT, 0);
        glBindVertexArray(0);
        glBindBufferARB(GL_ELEMENT_ARRAY_BUFFER_ARB, 0);
        glEndList();

        // TODO clenaup vertex buffers
    }

    fclose(meshFile);

    glBindBufferARB(GL_ARRAY_BUFFER_ARB, 0);
    glBindVertexArray(0);

    return true;
}

struct resource_cache mesh_resource_cache;

struct mesh* mesh_cache_load(const char* filename) {
    struct resource_cache_entry* entry = resource_cache_use(&mesh_resource_cache, filename);

    if (!entry->resource) {
        struct mesh* result = malloc(sizeof(struct mesh));
        
        mesh_load(result, filename);

        entry->resource = result;
    }

    return entry->resource;
}

void mesh_cache_release(struct mesh* mesh) {
    if (resource_cache_free(&mesh_resource_cache, mesh)) {
        for (int i = 0; i < mesh->submesh_count; ++i) {
            material_cache_release(mesh->materials[i]);
        }

        mesh_destroy(mesh);

        free(mesh);
    }
}