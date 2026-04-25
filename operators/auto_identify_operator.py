"""Operator: auto-identify skeleton bone roles by topology + geometry."""

import bpy
from ..properties import PREFIX
from ..skeleton_identifier import identify_skeleton, clear_cache


class OBJECT_OT_auto_identify_skeleton(bpy.types.Operator):
    """自动识别骨架角色（纯拓扑+几何，不依赖骨名）"""
    bl_idname = "object.xps_auto_identify_skeleton"
    bl_label = "Auto Identify Skeleton"

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "未选择骨架对象")
            return {'CANCELLED'}

        clear_cache()
        mapping = identify_skeleton(obj.data)

        from ..helper_classifier import classify_helpers
        cls = classify_helpers(obj.data, mapping)

        filled = 0
        for prop_name, bone_name in mapping.items():
            if bone_name and hasattr(context.scene, PREFIX + prop_name):
                setattr(context.scene, PREFIX + prop_name, bone_name)
                filled += 1

        # --- Logging (aligned with panel slots) ---
        from ..bone_map_and_group import mmd_bone_map
        print("\n========== [Auto Identify] 骨架自动识别结果 ==========")
        matched = []
        unmatched = []
        for prop_name, mmd_name in mmd_bone_map.items():
            xps_name = mapping.get(prop_name, "")
            if xps_name:
                matched.append(f"  {mmd_name:10s} ← {xps_name}")
            else:
                unmatched.append(f"  {mmd_name:10s} ← (未匹配)")

        print(f"--- 已匹配 ({len(matched)}) ---")
        for line in matched:
            print(line)

        if unmatched:
            print(f"--- 未匹配 ({len(unmatched)}) — 需手动设置或由补全骨骼创建 ---")
            for line in unmatched:
                print(line)

        # Classification summary
        from collections import Counter
        counts = Counter(cls.values())
        print(f"\n--- Helper 骨分类 ---")
        for cat in ("twist", "pelvis", "preserve", "other"):
            names = sorted([k for k, v in cls.items() if v == cat])
            if names:
                preview = ", ".join(names[:5])
                if len(names) > 5:
                    preview += f" (+{len(names) - 5})"
                print(f"  {cat:10s} {len(names):3d}  {preview}")

        print("=" * 50)

        total = sum(1 for v in mapping.values() if v)
        self.report({'INFO'}, f"自动识别完成: {total} 个骨骼角色已填充")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(OBJECT_OT_auto_identify_skeleton)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_auto_identify_skeleton)
