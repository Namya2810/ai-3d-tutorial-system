"""Synchronise the runtime scalpel/cutaway assets into the editable Blender source.

The imported collection is hidden by default because the web runtime controls when
the intact and dissected states are visible. Keeping both states in the .blend makes
future editing/export reproducible without showing duplicate kidneys at startup.
"""

from pathlib import Path
import math
import bpy
from mathutils import Vector


BLEND_PATH = Path(bpy.data.filepath)
MODEL_DIR = BLEND_PATH.parent
COLLECTION_NAME = "Interactive_Realistic_Assets"


def remove_collection(name):
    collection = bpy.data.collections.get(name)
    if not collection:
        return
    for obj in list(collection.all_objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(collection)


def imported_objects(before):
    return [obj for obj in bpy.data.objects if obj.name not in before]


def move_to_collection(objects, collection):
    for obj in objects:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)


def bounds(objects):
    points = []
    for obj in objects:
        if obj.type == "MESH":
            points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        return Vector((0, 0, 0)), Vector((1, 1, 1))
    low = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    return (low + high) * 0.5, high - low


def make_asset_parent(name, objects, target_size, location, rotation, role, state):
    center, size = bounds(objects)
    parent = bpy.data.objects.new(name, None)
    assets.objects.link(parent)
    parent.empty_display_type = "PLAIN_AXES"
    parent["interaction_role"] = role
    parent["scene_state"] = state
    parent["runtime_controlled"] = True
    largest = max(size)
    scale = target_size / largest if largest > 0 else 1.0
    for obj in objects:
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
        obj.location -= center
    parent.scale = (scale, scale, scale)
    parent.location = location
    parent.rotation_euler = rotation
    return parent


remove_collection(COLLECTION_NAME)
assets = bpy.data.collections.new(COLLECTION_NAME)
bpy.context.scene.collection.children.link(assets)

scalpel_reference = bpy.data.objects.get("Scalpel")
kidney_reference = bpy.data.objects.get("Kidney_Right")
scalpel_location = scalpel_reference.location.copy() if scalpel_reference else Vector((0, -1.4, 0.25))
kidney_location = kidney_reference.location.copy() if kidney_reference else Vector((1.3, 0, 0.35))

before = {obj.name for obj in bpy.data.objects}
bpy.ops.import_scene.gltf(filepath=str(MODEL_DIR / "Realistic_Scalpel.glb"))
scalpel_objects = imported_objects(before)
move_to_collection(scalpel_objects, assets)
make_asset_parent(
    "Interactive_Realistic_Scalpel",
    scalpel_objects,
    1.15,
    scalpel_location,
    (math.radians(8), math.radians(-5), math.radians(-12)),
    "precision_grip_tool",
    "DISSECTION_READY",
)

for name, offset, rotation, state in (
    ("Kidney_Attached_Open_Half", Vector((0, 0, 0)), (-math.pi / 2, 0, -0.10), "DISSECTION_DONE_ATTACHED"),
    ("Kidney_Removed_Half", Vector((0.9, -0.15, 0.05)), (math.pi / 2, 0, 0.16), "DISSECTION_DONE_REMOVED"),
):
    before = {obj.name for obj in bpy.data.objects}
    bpy.ops.import_scene.gltf(filepath=str(MODEL_DIR / "Kidney_Cutaway.glb"))
    objects = imported_objects(before)
    move_to_collection(objects, assets)
    make_asset_parent(
        name,
        objects,
        1.65,
        kidney_location + offset,
        rotation,
        "dissected_kidney_half",
        state,
    )

# Runtime starts with intact organs. These authoring assets are revealed by the
# app's scene-state controller, so prevent accidental duplicates in a direct render.
assets.hide_viewport = True
assets.hide_render = True

bpy.context.scene["interaction_gesture_contract"] = (
    "POINT=identify; PRECISION_GRAB(thumb-index pinch)=tool pickup; "
    "CLOSED_FIST_GRAB+motion=rotate; PINCH outside tool tasks=zoom; OPEN_HAND=release"
)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
print("SYNCED_REALISTIC_ASSETS", len(assets.all_objects), BLEND_PATH)
