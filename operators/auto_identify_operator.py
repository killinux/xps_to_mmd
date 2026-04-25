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

        filled = 0
        for prop_name, bone_name in mapping.items():
            if bone_name and hasattr(context.scene, PREFIX + prop_name):
                setattr(context.scene, PREFIX + prop_name, bone_name)
                filled += 1

        total = sum(1 for v in mapping.values() if v)
        self.report({'INFO'}, f"自动识别完成: {total} 个骨骼角色已填充")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(OBJECT_OT_auto_identify_skeleton)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_auto_identify_skeleton)
