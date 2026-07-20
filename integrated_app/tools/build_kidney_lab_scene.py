"""Build the editable top-view kidney lab scene from the current GLB.

Run with Blender in background mode. The script preserves imported kidney
objects/actions, replaces the exhibition slab with a lab table, adds a named
scalpel and cut-path markers, saves an editable .blend, and exports a new GLB.
"""

from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\Namya Jain\OneDrive\Desktop\ELC\integrated_app")
SOURCE_GLB = PROJECT / "ui/static/models/Biology_Kidney_Interactive_Session.glb"
OUTPUT_BLEND = PROJECT / "ui/static/models/Biology_Kidney_Lab_Table.blend"
OUTPUT_GLB = PROJECT / "ui/static/models/Biology_Kidney_Lab_Table.glb"


def material(name, color, metallic=0.0, roughness=0.55):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def cube(name, location, scale, mat, bevel=0.12):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("Soft_Edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    obj.data.materials.append(mat)
    return obj


def build_table():
    old_base = bpy.data.objects.get("Exhibit_Base")
    if old_base:
        bpy.data.objects.remove(old_base, do_unlink=True)

    top_mat = material("Lab_Table_Blue", (0.055, 0.22, 0.30), metallic=0.08, roughness=0.5)
    edge_mat = material("Lab_Table_Edge", (0.018, 0.07, 0.10), metallic=0.25, roughness=0.38)
    steel = material("Scalpel_Steel", (0.62, 0.73, 0.79), metallic=0.9, roughness=0.2)
    handle_mat = material("Scalpel_Handle", (0.04, 0.48, 0.58), metallic=0.35, roughness=0.34)

    table = cube("LAB_TABLE", (0.0, 0.0, -2.15), (7.8, 5.0, 0.22), top_mat, 0.18)
    table["scene_role"] = "lab_table"

    # Raised safety rim, useful visually from the top-view camera.
    cube("Table_Rim_Back", (0, 4.82, -1.82), (7.65, 0.12, 0.16), edge_mat, 0.06)
    cube("Table_Rim_Front", (0, -4.82, -1.82), (7.65, 0.12, 0.16), edge_mat, 0.06)
    cube("Table_Rim_Left", (-7.62, 0, -1.82), (0.12, 4.7, 0.16), edge_mat, 0.06)
    cube("Table_Rim_Right", (7.62, 0, -1.82), (0.12, 4.7, 0.16), edge_mat, 0.06)

    # Scalpel handle is the selectable parent mesh.
    scalpel = cube("Scalpel", (-0.6, -3.55, -1.62), (1.05, 0.16, 0.10), handle_mat, 0.11)
    scalpel.rotation_euler[2] = 0.12
    scalpel["interaction_role"] = "tool"

    blade = cube("Scalpel_Blade", (0.62, -3.40, -1.62), (0.38, 0.10, 0.055), steel, 0.035)
    blade.rotation_euler[2] = 0.12
    blade.parent = scalpel
    blade.matrix_parent_inverse = scalpel.matrix_world.inverted()

    # Exported empty nodes define the guided drag path over the left kidney.
    for name, location in (
        ("Cut_Path_Start", (-5.55, -0.85, -1.25)),
        ("Cut_Path_End", (-4.25, 0.95, -1.25)),
    ):
        empty = bpy.data.objects.new(name, None)
        empty.location = Vector(location)
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = 0.18
        empty["interaction_role"] = "cut_path_marker"
        bpy.context.scene.collection.objects.link(empty)

    state = bpy.data.objects.new("DISSECTION_READY", None)
    state["intact_object"] = "Kidney_Left"
    state["cutaway_object"] = "Renal_Cortex"
    state["tool"] = "Scalpel"
    bpy.context.scene.collection.objects.link(state)


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE_GLB))
    build_table()

    # Save a real editable Blender source for the next iteration.
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))

    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT_GLB),
        export_format="GLB",
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
    )
    print(f"LAB_BLEND={OUTPUT_BLEND}")
    print(f"LAB_GLB={OUTPUT_GLB}")


if __name__ == "__main__":
    main()
