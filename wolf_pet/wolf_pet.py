"""
Wolf Desktop Pet - 3D + Head Gaze Edition
安装：pip install PyQt6 Pillow
运行：python wolf_pet.py

操作：
  左键拖动        → 移动
  右键左右拖动    → 旋转360°视角
  双指左右滑动    → 旋转视角（macOS）
  右键单击        → 菜单（视线跟随开关 / 关闭）
"""

import sys, os, math, time, random
from PIL import Image, ImageDraw, ImageFilter
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QMenu
from PyQt6.QtGui     import QPixmap, QImage, QCursor, QAction
from PyQt6.QtCore    import Qt, QTimer, QPoint

FRAMES_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
SPRITE_SIZE       = 228
FPS               = 12
NUM_ANGLES        = 12
ROTATE_PX         = 18
MOUSE_IDLE_SEC    = 10.0
GAZE_NAMES        = ["rr", "r", "fwd", "l", "ll"]   # 右右/右/正/左/左左


# ─── 阴影 ────────────────────────────────────
def _add_shadow(img: Image.Image) -> Image.Image:
    """方向性投影阴影：光从左前上方，影子向右延伸落地。"""
    import numpy as np

    w, h = img.size
    arr = np.array(img)

    # 取狼的轮廓（alpha 通道）
    silhouette = arr[:, :, 3].astype(np.float32) / 255.0

    # 将轮廓投影到地面：垂直压扁 + 向右偏移（模拟左前上方光源）
    proj_h = max(1, int(h * 0.18))      # 投影高度（压扁）
    offset_x = int(w * 0.18)            # 向右偏移
    foot_y = int(h * 0.88)              # 脚底位置

    # 把轮廓压缩后放置在脚底
    from PIL import Image as PILImage
    sil_img = PILImage.fromarray((silhouette * 255).astype(np.uint8), 'L')
    proj = sil_img.resize((w, proj_h), PILImage.LANCZOS)

    # 合成投影阴影层
    sh_arr = np.zeros((h, w, 4), dtype=np.uint8)
    y0 = foot_y - proj_h // 2
    y1 = y0 + proj_h
    y0c, y1c = max(0, y0), min(h, y1)
    py0 = y0c - y0

    proj_arr = np.array(proj)
    for row in range(y0c, y1c):
        pr = proj_arr[row - y0c + py0]
        x_start = max(0, offset_x)
        x_end   = min(w, w + offset_x)
        src_start = x_start - offset_x
        sh_arr[row, x_start:x_end, 3] = np.maximum(
            sh_arr[row, x_start:x_end, 3],
            (pr[src_start: src_start + (x_end - x_start)] * 0.55).astype(np.uint8)
        )

    # 模糊柔化
    sh_img = PILImage.fromarray(sh_arr, 'RGBA')
    sh_img = sh_img.filter(ImageFilter.GaussianBlur(radius=4))

    out = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(sh_img)
    out.alpha_composite(img)
    return out


# ─── 帧工具 ──────────────────────────────────
def _pil_to_qpixmap(img):
    if img.mode != "RGBA": img = img.convert("RGBA")
    data = img.tobytes("raw","RGBA")
    qi   = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qi)

def _load_seq(subdir, size=None):
    path = os.path.join(FRAMES_DIR, subdir)
    if not os.path.isdir(path): return []
    files = sorted(f for f in os.listdir(path) if f.endswith(".png"))
    imgs  = []
    for f in files:
        im = Image.open(os.path.join(path,f)).convert("RGBA")
        if size: im = im.resize((size,size), Image.LANCZOS)
        imgs.append(im)
    return imgs


# ─── 桌宠 ────────────────────────────────────
class WolfPet(QWidget):

    def __init__(self):
        super().__init__()
        self._load_frames()
        self._setup_window()
        self._init_state()
        t = QTimer(self); t.timeout.connect(self._tick); t.start(1000//FPS)

    # ── 加载 ─────────────────────────────────
    def _load_frames(self):
        print("加载帧...", flush=True)
        sz = SPRITE_SIZE

        # 身体帧  body_00..11 / 0000..0023
        self._body = []
        for ai in range(NUM_ANGLES):
            seq = _load_seq(f"body_{ai:02d}", sz)
            self._body.append(seq)
            print(f"  body_{ai:02d}: {len(seq)}帧", flush=True)

        # 头部帧  head_00..11_rr/r/fwd/l/ll / 0000..0023
        self._head = []          # [angle][gaze] = [frames]
        for ai in range(NUM_ANGLES):
            row = []
            for gn in GAZE_NAMES:
                seq = _load_seq(f"head_{ai:02d}_{gn}", sz)
                row.append(seq)
            self._head.append(row)
            print(f"  head_{ai:02d}: {[len(r) for r in row]}帧", flush=True)

        # 合成缓存：body+head 按需计算，不提前存储
        self._composite_cache = {}

        print("加载完成", flush=True)

    def _get_frame(self, angle_idx, gaze_idx, frame_idx):
        """合成身体+头部，带缓存"""
        key = (angle_idx, gaze_idx, frame_idx)
        if key in self._composite_cache:
            return self._composite_cache[key]

        body_seq = self._body[angle_idx]
        head_seq = self._head[angle_idx][gaze_idx]

        if not body_seq:
            return None

        body_img = body_seq[frame_idx % len(body_seq)]

        if not head_seq:
            result = body_img.copy()
        else:
            h_img = head_seq[frame_idx % len(head_seq)]
            result = body_img.copy()
            result.alpha_composite(h_img)

        self._composite_cache[key] = result
        return result

    # ── 窗口 ─────────────────────────────────
    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint        |
            Qt.WindowType.WindowStaysOnTopHint       |
            Qt.WindowType.WindowDoesNotAcceptFocus   # 点击不抢焦点
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(SPRITE_SIZE, SPRITE_SIZE)
        self._label = QLabel(self)
        self._label.setGeometry(0,0,SPRITE_SIZE,SPRITE_SIZE)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.width()//2-SPRITE_SIZE//2, scr.height()//2-SPRITE_SIZE//2)

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == 'darwin':
            self._macos_set_floating()

    def _macos_set_floating(self):
        """macOS：把窗口设为 NSFloatingWindowLevel，永远浮在其他应用上方"""
        try:
            import ctypes, ctypes.util
            libobjc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
            libobjc.sel_registerName.restype  = ctypes.c_void_p
            libobjc.sel_registerName.argtypes = [ctypes.c_char_p]

            # [nsview window] → NSWindow
            libobjc.objc_msgSend.restype  = ctypes.c_void_p
            libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            nsview = int(self.winId())
            nswin  = libobjc.objc_msgSend(
                         nsview, libobjc.sel_registerName(b'window'))

            # [nswin setLevel: NSFloatingWindowLevel(3)]
            libobjc.objc_msgSend.argtypes = [ctypes.c_void_p,
                                              ctypes.c_void_p, ctypes.c_long]
            libobjc.objc_msgSend(nswin,
                libobjc.sel_registerName(b'setLevel:'), ctypes.c_long(3))

            # 出现在所有 Space，不随 Mission Control 最小化
            libobjc.objc_msgSend(nswin,
                libobjc.sel_registerName(b'setCollectionBehavior:'),
                ctypes.c_long(1 | 16))
        except Exception as e:
            print(f"macOS 浮动窗口设置失败: {e}")

    # ── 状态 ─────────────────────────────────
    def _init_state(self):
        self._frame_idx      = 0
        self._angle_idx      = 0
        self._gaze_idx       = 2          # 2 = fwd（正中）
        self._gaze_follow    = False

        self._dragging       = False
        self._drag_offset    = QPoint()
        self._rotating       = False
        self._rot_start_x    = 0
        self._rot_base       = 0
        self._right_moved    = False

        self._mouse_global      = QCursor.pos()
        self._last_mouse_move   = time.time()
        self._mouse_idle        = False

    # ── 主循环 ───────────────────────────────
    def _tick(self):
        self._update_mouse()
        if self._gaze_follow:
            self._update_gaze()
        self._frame_idx = (self._frame_idx + 1) % 24
        self._draw()

    def _update_mouse(self):
        pos = QCursor.pos()
        if pos != self._mouse_global:
            self._mouse_global    = pos
            self._last_mouse_move = time.time()
            self._mouse_idle      = False
        else:
            self._mouse_idle = (time.time()-self._last_mouse_move) > MOUSE_IDLE_SEC

    def _update_gaze(self):
        """根据鼠标相对窗口中心的水平偏移选择视线方向"""
        if self._mouse_idle or self._rotating:
            self._gaze_idx = 2   # 回正
            return
        dx = self._mouse_global.x() - self.geometry().center().x()
        if   dx < -120: self._gaze_idx = 4   # 远左
        elif dx <  -40: self._gaze_idx = 3   # 近左
        elif dx <   40: self._gaze_idx = 2   # 正前
        elif dx <  120: self._gaze_idx = 1   # 近右
        else:           self._gaze_idx = 0   # 远右

    def _draw(self):
        gaze = self._gaze_idx if self._gaze_follow else 2
        img  = self._get_frame(self._angle_idx, gaze, self._frame_idx)
        if img:
            self._label.setPixmap(_pil_to_qpixmap(img))

    # ── 鼠标事件 ─────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging    = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self._rotating   = True
            self._right_moved = False
            self._rot_start_x = event.globalPosition().toPoint().x()
            self._rot_base    = self._angle_idx
        event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_offset
            self.move(new_pos)
        if self._rotating and event.buttons() & Qt.MouseButton.RightButton:
            dx = event.globalPosition().toPoint().x() - self._rot_start_x
            if abs(dx) > 4: self._right_moved = True
            self._angle_idx = (self._rot_base + dx//ROTATE_PX) % NUM_ANGLES
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
        elif event.button() == Qt.MouseButton.RightButton:
            self._rotating = False
            if not self._right_moved:
                menu = QMenu(self)
                label = "✓ 视线跟随（开）" if self._gaze_follow else "  视线跟随（关）"
                ga = QAction(label, self); ga.triggered.connect(self._toggle_gaze)
                menu.addAction(ga)
                menu.addSeparator()
                qa = QAction("关闭桌宠", self); qa.triggered.connect(QApplication.quit)
                menu.addAction(qa)
                menu.exec(event.globalPosition().toPoint())
            self._right_moved = False
        event.accept()

    def wheelEvent(self, event):
        dx = event.angleDelta().x()
        dy = event.angleDelta().y()
        delta = dx if abs(dx) > abs(dy) else dy
        if   delta >  30: self._angle_idx = (self._angle_idx-1) % NUM_ANGLES
        elif delta < -30: self._angle_idx = (self._angle_idx+1) % NUM_ANGLES
        event.accept()

    def _toggle_gaze(self):
        self._gaze_follow = not self._gaze_follow
        if not self._gaze_follow:
            self._gaze_idx = 2   # 关闭时回正
        self._composite_cache.clear()   # 清缓存触发重绘


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # macOS：设为 Accessory 应用，不出现在 Dock/Cmd+Tab，不抢应用焦点
    if sys.platform == 'darwin':
        try:
            import ctypes, ctypes.util
            libobjc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
            libobjc.objc_getClass.restype  = ctypes.c_void_p
            libobjc.objc_getClass.argtypes = [ctypes.c_char_p]
            libobjc.sel_registerName.restype  = ctypes.c_void_p
            libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
            libobjc.objc_msgSend.restype  = ctypes.c_void_p
            libobjc.objc_msgSend.argtypes = [ctypes.c_void_p,
                                              ctypes.c_void_p, ctypes.c_long]
            NSApp_class = libobjc.objc_getClass(b'NSApplication')
            sel_shared  = libobjc.sel_registerName(b'sharedApplication')
            libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            nsapp = libobjc.objc_msgSend(NSApp_class, sel_shared)
            # NSApplicationActivationPolicyAccessory = 1
            libobjc.objc_msgSend.argtypes = [ctypes.c_void_p,
                                              ctypes.c_void_p, ctypes.c_long]
            libobjc.objc_msgSend(nsapp,
                libobjc.sel_registerName(b'setActivationPolicy:'),
                ctypes.c_long(1))
        except Exception as e:
            print(f"macOS Accessory 模式设置失败: {e}")

    pet = WolfPet()
    pet.show()
    sys.exit(app.exec())
