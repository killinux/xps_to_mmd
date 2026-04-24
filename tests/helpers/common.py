"""Common helpers used by all phases."""
import json
import os
from pathlib import Path


def clean_scene():
    """Completely reset Blender scene (safer than read_factory_settings — keeps addons)."""
    import bpy
    # Remove all objects
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    # Purge orphan data
    try:
        bpy.ops.outliner.orphans_purge(do_recursive=True)
    except Exception:
        pass


def ensure_out_dir(iter_n, base="/opt/mywork/xps_to_mmd/out"):
    p = Path(base) / f"iter-{iter_n}"
    p.mkdir(parents=True, exist_ok=True)
    (p / "screenshots").mkdir(exist_ok=True)
    return p


def jwrite(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def mdwrite(path, text):
    Path(path).write_text(text)


def find_armature(prefer=None):
    import bpy
    if prefer and prefer in bpy.data.objects and bpy.data.objects[prefer].type == 'ARMATURE':
        return bpy.data.objects[prefer]
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    if not arms:
        return None
    return arms[0]


def set_active(obj):
    import bpy
    bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.mode != 'OBJECT' else None
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


# MMD canonical bone names that we assert must exist after main pipeline
CORE_MMD_BONES = [
    "全ての親", "センター", "グルーブ", "腰",
    "上半身", "上半身2", "上半身3", "首", "頭",
    "左肩", "右肩", "左腕", "右腕", "左ひじ", "右ひじ", "左手首", "右手首",
    "下半身",
    "左足", "右足", "左ひざ", "右ひざ", "左足首", "右足首",
]
