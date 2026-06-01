"""
Wolf Desktop Pet - Blender Rendering Script
在 Blender 的 Scripting 标签页粘贴并运行。
渲染出三组帧：头部朝前、朝左、朝右，共 3×24 = 72 帧 + 1 帧待机。
"""

import bpy
import os
import math

# ──────────────────────────────────────
# 配置
# ──────────────────────────────────────
OUTPUT_DIR   = "/Users/talia/Desktop/untitled folder/wolf_pet/frames"
RESOLUTION   = 256          # 正方形
ORTHO_SCALE  = 0.72         # 调小 = 画面中狼更大
RUN_START    = 0            # 跑步循环起始帧
RUN_END      = 23           # 跑步循环结束帧（含）
IDLE_FRAME   = 121          # 待机帧

# 头部水平转角（Z轴旋转），三个状态
HEAD_ANGLES = {
    "fwd":   0.0,
    "left":  math.radians(30),
    "right": math.radians(-30),
}

# 头部控制节点
HEAD_CTRL  = "Box006.011_7"
HEAD_BLOCK = "Box006.010_6"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ──────────────────────────────────────
# 摄像机：正视图稍微偏右上方
# ──────────────────────────────────────
cam_obj = bpy.data.objects.get("WolfPetCam")
if not cam_obj:
    cam_data = bpy.data.cameras.new("WolfPetCam")
    cam_data.type       = 'ORTHO'
    cam_data.ortho_scale = ORTHO_SCALE
    cam_obj = bpy.data.objects.new("WolfPetCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
else:
    cam_obj.data.ortho_scale = ORTHO_SCALE

# 位置：从正面偏右上俯视
cam_obj.location        = (0.15, -2.5, 0.55)
cam_obj.rotation_euler  = (math.radians(87), 0, math.radians(4))
bpy.context.scene.camera = cam_obj

# ──────────────────────────────────────
# 渲染参数
# ──────────────────────────────────────
scene = bpy.context.scene
scene.render.resolution_x              = RESOLUTION
scene.render.resolution_y              = RESOLUTION
scene.render.resolution_percentage     = 100
scene.render.film_transparent          = True
scene.render.image_settings.file_format  = 'PNG'
scene.render.image_settings.color_mode  = 'RGBA'
scene.render.image_settings.compression = 15

# ──────────────────────────────────────
# 渲染函数
# ──────────────────────────────────────
total = len(HEAD_ANGLES) * (RUN_END - RUN_START + 1) + 1
done  = 0

def render(path, frame, head_z_rot):
    """设帧、设头部角度、渲染"""
    scene.frame_set(frame)

    hc = bpy.data.objects.get(HEAD_CTRL)
    hb = bpy.data.objects.get(HEAD_BLOCK)
    if hc:
        hc.rotation_euler[2] = head_z_rot
    if hb:
        hb.rotation_euler[2] = head_z_rot

    bpy.context.view_layer.update()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

# ──────────────────────────────────────
# 渲染跑步帧（三个头部方向）
# ──────────────────────────────────────
for direction, angle in HEAD_ANGLES.items():
    subdir = os.path.join(OUTPUT_DIR, f"run_{direction}")
    os.makedirs(subdir, exist_ok=True)
    for f in range(RUN_START, RUN_END + 1):
        out = os.path.join(subdir, f"{f:04d}.png")
        render(out, f, angle)
        done += 1
        print(f"[{done}/{total}] run_{direction} 帧{f}")

# ──────────────────────────────────────
# 渲染待机帧（头部朝前）
# ──────────────────────────────────────
idle_dir = os.path.join(OUTPUT_DIR, "idle")
os.makedirs(idle_dir, exist_ok=True)
render(os.path.join(idle_dir, "0000.png"), IDLE_FRAME, 0.0)
done += 1
print(f"[{done}/{total}] idle 帧{IDLE_FRAME}")

# ──────────────────────────────────────
# 恢复头部旋转
# ──────────────────────────────────────
for name in [HEAD_CTRL, HEAD_BLOCK]:
    obj = bpy.data.objects.get(name)
    if obj:
        obj.rotation_euler[2] = 0.0

print(f"\n✅ 渲染完成！帧保存于:\n   {OUTPUT_DIR}")
