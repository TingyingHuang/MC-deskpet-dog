"""
Wolf Desktop Pet - HD 渲染脚本 (512px)
在 Blender 的 Scripting 标签页粘贴并运行。
渲染 12 角度 × 24 帧 × (1 body + 5 head gaze) = 1728 帧
"""

import bpy, os, math

OUTPUT_DIR  = "/Users/talia/Desktop/untitled folder/wolf_pet/frames"
RESOLUTION  = 512
ORTHO_SCALE = 0.72
NUM_ANGLES  = 12
RUN_START   = 0
RUN_END     = 23
ANGLE_STEP  = 360.0 / NUM_ANGLES

HEAD_GAZE = {
    "fwd": 0.0,
    "l":   math.radians(20),
    "ll":  math.radians(40),
    "r":   math.radians(-20),
    "rr":  math.radians(-40),
}

HEAD_CTRL  = "Box006.011_7"
HEAD_BLOCK = "Box006.010_6"

scene = bpy.context.scene
scene.render.resolution_x             = RESOLUTION
scene.render.resolution_y             = RESOLUTION
scene.render.resolution_percentage    = 100
scene.render.film_transparent         = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode  = 'RGBA'
scene.render.image_settings.compression = 15
scene.render.use_freestyle            = False
scene.render.filter_size              = 0.5
for vl in scene.view_layers:
    vl.use_freestyle = False

cam_obj = bpy.data.objects.get("WolfPetCam")
if not cam_obj:
    cam_data = bpy.data.cameras.new("WolfPetCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ORTHO_SCALE
    cam_obj = bpy.data.objects.new("WolfPetCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
else:
    cam_obj.data.ortho_scale = ORTHO_SCALE
bpy.context.scene.camera = cam_obj

def render(path, frame, head_z, cam_rot_z):
    scene.frame_set(frame)
    cam_obj.location       = (0.15, -2.5, 0.55)
    cam_obj.rotation_euler = (math.radians(87), 0, math.radians(cam_rot_z))
    for name in [HEAD_CTRL, HEAD_BLOCK]:
        obj = bpy.data.objects.get(name)
        if obj: obj.rotation_euler[2] = head_z
    bpy.context.view_layer.update()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

total = NUM_ANGLES * (RUN_END - RUN_START + 1) * (1 + len(HEAD_GAZE))
done  = 0

for ai in range(NUM_ANGLES):
    cam_z   = 4 + ai * ANGLE_STEP
    dst_dir = os.path.join(OUTPUT_DIR, f"body_{ai:02d}")
    os.makedirs(dst_dir, exist_ok=True)
    for f in range(RUN_START, RUN_END + 1):
        render(os.path.join(dst_dir, f"{f:04d}.png"), f, 0.0, cam_z)
        done += 1
    print(f"[{done}/{total}] body_{ai:02d}")

for ai in range(NUM_ANGLES):
    cam_z = 4 + ai * ANGLE_STEP
    for gname, gz in HEAD_GAZE.items():
        dst_dir = os.path.join(OUTPUT_DIR, f"head_{ai:02d}_{gname}")
        os.makedirs(dst_dir, exist_ok=True)
        for f in range(RUN_START, RUN_END + 1):
            render(os.path.join(dst_dir, f"{f:04d}.png"), f, gz, cam_z)
            done += 1
        print(f"[{done}/{total}] head_{ai:02d}_{gname}")

cam_obj.rotation_euler = (math.radians(87), 0, math.radians(4))
for name in [HEAD_CTRL, HEAD_BLOCK]:
    obj = bpy.data.objects.get(name)
    if obj: obj.rotation_euler[2] = 0.0

print(f"\n✅ 渲染完成！共 {total} 帧 @ 512px\n   {OUTPUT_DIR}")
