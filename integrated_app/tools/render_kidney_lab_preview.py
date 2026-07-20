"""Render a quick QA preview of the generated kidney lab .blend."""

from pathlib import Path

import bpy
from mathutils import Vector


OUTPUT = Path(r"C:\Users\Namya Jain\OneDrive\Desktop\ELC\integrated_app\kidney_lab_preview.png")


def point_at(obj, target=(0, 0, -1.0)):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


world = bpy.context.scene.world
world.color = (0.012, 0.018, 0.028)

bpy.ops.object.camera_add(location=(0, -13.5, 15.5))
camera = bpy.context.object
camera.data.lens = 52
point_at(camera)
bpy.context.scene.camera = camera

bpy.ops.object.light_add(type="AREA", location=(0, -2, 12))
key = bpy.context.object
key.data.energy = 1500
key.data.shape = "DISK"
key.data.size = 9

bpy.ops.object.light_add(type="AREA", location=(-8, -2, 5))
fill = bpy.context.object
fill.data.energy = 850
fill.data.size = 7
point_at(fill)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(OUTPUT)
scene.render.film_transparent = False
bpy.ops.render.render(write_still=True)
print(f"PREVIEW={OUTPUT}")
