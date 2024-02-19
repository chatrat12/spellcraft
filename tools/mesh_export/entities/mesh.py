import bpy
import mathutils
from . import material
from . import serialize
import os
import struct
import bmesh
import sys
import math

class mesh_data():
    def __init__(self, mat: bpy.types.Material) -> None:
        self.mat: bpy.types.Material = mat
        self.vertices = []
        self.normals = []
        self.color = []
        self.uv = []
        self.indices = []

    def append_mesh(self, mesh: bpy.types.Mesh, material_index: int, final_transform: mathutils.Matrix):
        triangles = []
        max_index = -1
        used_indices = set()

        normal_transform = final_transform.to_3x3()
        normal_transform.invert()
        normal_transform.transpose()

        for polygon in mesh.polygons:
            if polygon.material_index != material_index:
                continue
            
            for loop_index in polygon.loop_indices:
                max_index = max(max_index, loop_index)
                used_indices.add(loop_index)
                
            triangles.append(polygon.loop_indices[0])
            triangles.append(polygon.loop_indices[1])
            triangles.append(polygon.loop_indices[2])

        next_output = len(self.indices)
        index_mapping = dict()

        uv_layer = None if len(mesh.uv_layers) == 0 else mesh.uv_layers[0]

        color = None

        for attr in mesh.attributes:
            if attr.data_type == 'BYTE_COLOR' or attr.data_type == 'FLOAT_COLOR':
                color = attr

        for loop_index in range(max_index + 1):
            if not loop_index in used_indices:
                continue

            vtx_index = mesh.loops[loop_index].vertex_index

            pos = final_transform @ mesh.vertices[vtx_index].co
            pos[0] = -pos[0]
            self.vertices.append(pos)
            self.normals.append(normal_transform @ mesh.vertices[vtx_index].normal)

            if uv_layer:
                self.uv.append(mesh.uv_layers[0].uv[loop_index].vector)
            else:
                self.uv.append([0, 0])

            if color and color.domain == 'CORNER':
                self.color.append(color.data[loop_index].color)
            elif color and color.domain == 'POINT':
                self.color.append(color.data[vtx_index].color)

            index_mapping[loop_index] = next_output
            next_output += 1
        
        for idx in triangles:
            self.indices.append(index_mapping[idx])

def search_node_input(from_node: bpy.types.Node, input_name: str):
    for input in from_node.inputs:
        if input.name == input_name:
            return input
        
    return None


def search_node_linkage(from_node: bpy.types.Node, input_name: str):
    input = search_node_input(from_node, input_name)

    if not input.is_linked:
        return None

    for link in input.links:
        return link.from_node
        
    return None

def find_node_of_type(tree_nodes: bpy.types.Nodes, type_name: str):
    for node in tree_nodes:
        if node.type == type_name:
            return node
        
    return None

def color_float_to_int(value):
    result = int(value * 255)

    if result > 255:
        result = 255
    elif result < 0:
        result = 0

    return result

def color_array_to_color(array):
    return material.Color(
        color_float_to_int(array[0]),
        color_float_to_int(array[1]),
        color_float_to_int(array[2]),
        color_float_to_int(array[3])
    )

def determine_material_from_nodes(mat: bpy.types.Material, result: material.Material):
    output_node = find_node_of_type(mat.node_tree.nodes, 'OUTPUT_MATERIAL')

    if not output_node:
        print('Could not find output node for material')
        return

    material_type = search_node_linkage(output_node, 'Surface')

    if not material_type:
        print('No input was specified for output material')
        return

    color_link: bpy.types.NodeSocket | None = None

    if material_type.type == 'BSDF_PRINCIPLED':
        color_link = search_node_input(material_type, 'Base Color')
        emmission_link = search_node_input(material_type, 'Emission Color')
        result.lighting = True

        if not color_link.is_linked and emmission_link.is_linked:
            color_link = emmission_link
            result.lighting = False

    elif material_type.type == 'BSDF_DIFFUSE':
        color_link = search_node_input(material_type, 'Color')
        result.lighting = True
    elif material_type.type == 'EMISSION':
        color_link = search_node_input(material_type, 'Color')
        result.lighting = False
    elif material_type.type == 'MIX':
        color_link = search_node_input(output_node, 'Surface')
        result.lighting = False
    else:
        print(f"The node type {material_type.type} is not supported")
        return

    if not color_link:
        print('couldnt find color link')
        return
    
    # TODO determine alpha

    color_name = 'PRIM'
    
    # solid color
    if not color_link.is_linked:
        color = color_link.default_value
        result.prim_color = color_array_to_color(color)
        color_name = 'PRIM'
    elif color_link.links[0].from_node.type == 'TEX_IMAGE':
        color_node: bpy.types.ShaderNodeTexImage = color_link.links[0].from_node
        color_name = 'TEX0'

        input_filename = sys.argv[1]
        image_path = os.path.normpath(os.path.join(os.path.dirname(input_filename), color_node.image.filepath[2:]))

        result.tex0 = material.Tex()
        result.tex0.filename = image_path

        if color_node.interpolation == 'Nearest':
            result.tex0.min_filter = 'nearest'
            result.tex0.mag_filter = 'nearest'
        else:
            result.tex0.min_filter = 'linear'
            result.tex0.mag_filter = 'linear'

        if color_node.extension == 'REPEAT':
            result.tex0.s.repeats = 2048
            result.tex0.s.mirror = False
            result.tex0.t.repeats = 2048
            result.tex0.t.mirror = False
        elif color_node.extension == 'MIRROR':
            result.tex0.s.repeats = 2048
            result.tex0.s.mirror = True
            result.tex0.t.repeats = 2048
            result.tex0.t.mirror = True
        else:
            result.tex0.s.repeats = 1
            result.tex0.s.mirror = False
            result.tex0.t.repeats = 1
            result.tex0.t.mirror = False

    if result.lighting:
        result.combine_mode = material.CombineMode(
            material.CombineModeCycle(
                color_name, '0', 'SHADE', '0',
                color_name, '0', 'SHADE', '0'
            ),
            None
        )
    else:
        result.combine_mode = material.CombineMode(
            material.CombineModeCycle(
                '0', '0', '0', color_name,
                '0', '0', '0', color_name
            ),
            None
        )

    if mat.use_backface_culling:
        result.culling = True
    else:
        result.culling = False

    if mat.blend_method == 'CLIP':
        result.blend_mode = material.BlendMode(material.BlendModeCycle('IN', '0', 'IN', '1'), None)
        result.blend_mode.alpha_compare = 'THRESHOLD'
        result.blend_color = material.Color(0, 0, 0, 128)
    elif mat.blend_method == 'BLEND':
        result.blend_mode = material.BlendMode(material.BlendModeCycle('IN', 'IN_A', 'MEMORY', 'INV_MUX_A'), None)
        result.blend_mode.z_write = False
    elif mat.blend_method == 'HASHED':
        result.blend_mode = material.BlendMode(material.BlendModeCycle('IN', '0', 'IN', '1'), None)
        result.blend_mode.alpha_compare = 'NOISE'
    else:
        result.blend_mode = material.BlendMode(material.BlendModeCycle('IN', '0', 'IN', '1'), None)

    if 'decal' in mat and mat['decal']:
        result.blend_mode.z_mode = 'DECAL'
        result.blend_mode.z_write = False

    
def convert_vertex_channel(input, gamma):
    result = int(255 * math.pow(input, gamma))

    if result > 255:
        return 255
    elif result < 0:
        return 0
    
    return result

ATTR_POS = 1 << 0
ATTR_UV = 1 << 1
ATTR_COLOR = 1 << 2
ATTR_NORMAL = 1 << 3

def write_meshes(file, mesh_list):
    file.write('MESH'.encode())
    file.write(len(mesh_list).to_bytes(1, 'big'))

    for mesh_pair in mesh_list:
        material_name = mesh_pair[0]
        mesh: mesh_data = mesh_pair[1]

        material_filename = f"assets/{material_name}.mat.json"

        if not material_name.startswith('materials/'):
            # embedded material
            material_object = material.Material()

            if mesh.mat.use_nodes:
                determine_material_from_nodes(mesh.mat, material_object)

            print(f"embedding material {material_name}")

            # signal an embedded material
            file.write((0).to_bytes(1, 'big'))

            serialize.serialize_material_file(file, material_object)

        elif os.path.exists(material_filename):
            print(f"using existing material {material_filename}")
            material_object = material.parse_material(material_filename)

            material_romname = f"rom:/{material_name}.mat".encode()
            file.write(len(material_romname).to_bytes(1, 'big'))
            file.write(material_romname)
        else:
            raise Exception(f"{material_filename} does not exist")
    
        needs_uv = bool(material_object.tex0)
        needs_normal = bool(material_object.lighting)
        needs_color = len(mesh.color) > 0

        attribute_mask = ATTR_POS

        if needs_uv:
            attribute_mask |= ATTR_UV

        if needs_color:
            attribute_mask |= ATTR_COLOR

        if needs_normal:
            attribute_mask |= ATTR_NORMAL

        file.write((attribute_mask).to_bytes(1, 'big'))

        # TODO deduplicate vertices
        # TODO optimize triangle order

        file.write(len(mesh.vertices).to_bytes(2, 'big'))
        for idx, vertex in enumerate(mesh.vertices):
            file.write(struct.pack(
                ">hhh", 
                int(vertex[0] * 32), 
                int(vertex[1] * 32), 
                int(vertex[2] * 32)
            ))

            if needs_uv:
                uv = mesh.uv[idx]

                file.write(struct.pack(
                    ">hh",
                    int(uv[0] * 256),
                    int((1 - uv[1]) * 256)
                ))

            if needs_color:
                color = mesh.color[idx]

                file.write(struct.pack(
                    ">BBBB", 
                    convert_vertex_channel(color[0], material_object.vertex_gamma), 
                    convert_vertex_channel(color[1], material_object.vertex_gamma), 
                    convert_vertex_channel(color[2], material_object.vertex_gamma), 
                    convert_vertex_channel(color[3], 1)
                ))

            if needs_normal:
                normal = mesh.normals[idx].normalized()

                file.write(struct.pack(
                    ">bbb", 
                    int(normal[0] * 127), 
                    int(normal[1] * 127), 
                    int(normal[2] * 127)
                ))

        index_size = 1

        if len(mesh.vertices) > 256:
            index_size = 2

        file.write(len(mesh.indices).to_bytes(2, 'big'))

        for index in mesh.indices:
            file.write(index.to_bytes(index_size, 'big'))

class mesh_list():
    def __init__(self) -> None:
        self.meshes = []

    def append(self, mesh, transform):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        result_mesh = bpy.data.meshes.new(f"{mesh.name}_triangulated")
        bm.to_mesh(mesh)
        bm.free()
        self.meshes.append([mesh, transform])

    def write_mesh(self, write_to):
        mesh_by_material = dict()

        for pair in self.meshes:
            mesh = pair[0]
            transform = pair[1]

            for material_index in range(max(len(mesh.materials), 1)):
                if material_index < len(mesh.materials):
                    mat = mesh.materials[material_index]
                    name = mat.name
                else:
                    mat = None
                    name = ""

                if not name in mesh_by_material:
                    mesh_by_material[name] = mesh_data(mat)

                mesh_data_instance = mesh_by_material[name]

                mesh_data_instance.append_mesh(mesh, material_index, transform)

        all_meshes = list(mesh_by_material.items())

        all_meshes.sort(key=lambda x: x[0])

        write_meshes(write_to, all_meshes)