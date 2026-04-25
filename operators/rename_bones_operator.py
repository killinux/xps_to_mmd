import bpy
from .. import bone_map_and_group
from .. import preset_operator
from .. import bone_utils
from ..properties import PREFIX


class OBJECT_OT_rename_to_mmd(bpy.types.Operator):
    """将选定的骨骼重命名为 MMD 格式"""
    bl_idname = "object.xps_rename_to_mmd"
    bl_label = "Rename to MMD"

    mmd_bone_map = bone_map_and_group.mmd_bone_map  # 使用导入的bone_map模块

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "没有选择骨架对象")
            return {'CANCELLED'}

        # 创建骨架备份
        # 使用直接的方式复制对象，避免上下文问题
        backup_data = obj.data.copy()
        backup_data.name = f"{obj.data.name}_backup"
        backup_obj = bpy.data.objects.new(f"{obj.name}_backup", backup_data)
        bpy.context.collection.objects.link(backup_obj)
        
        # 设置备份对象的属性
        backup_obj.matrix_world = obj.matrix_world
        backup_obj.hide_viewport = True
        backup_obj.hide_render = True
        
        self.report({'INFO'}, f"已创建骨架备份: {backup_obj.name} (数据块: {backup_obj.data.name})")

        # 检测骨架高度并自动缩放
        scaled, scale_factor, skeleton_height = bone_utils.check_and_scale_skeleton(obj)
        
        if scaled:
            self.report({'INFO'}, f"骨架高度为 {skeleton_height:.2f}m，已缩放 {scale_factor:.3f} 倍")

        scene = context.scene
        # 检查选择框里是否有骨骼设置
        has_bone_set = False
        for prop_name in preset_operator.get_bones_list():  # 从operations.py中获取骨骼属性名称列表
            if getattr(scene, PREFIX + prop_name, None):
                has_bone_set = True
                break
        if not has_bone_set:
            self.report({'WARNING'}, "未设置骨骼")
            return {'CANCELLED'}
        rename_map = {}
        for prop_name, new_name in self.mmd_bone_map.items():
            bone_name = getattr(scene, PREFIX + prop_name, None)
            if bone_name:
                bone = obj.pose.bones.get(bone_name)
                if bone:
                    if bone.name != new_name:
                        old_name = bone.name
                        bone.name = new_name
                        rename_map[old_name] = new_name
                        setattr(scene, PREFIX + prop_name, new_name)
                else:
                    self.report({'WARNING'}, f"未找到骨骼 '{bone_name}' 以重命名为 {new_name}")

        if rename_map:
            mesh_objects = [
                o for o in bpy.data.objects
                if o.type == 'MESH' and any(
                    m.type == 'ARMATURE' and m.object == obj for m in o.modifiers
                )
            ]
            vg_fixed = 0
            for mesh in mesh_objects:
                for old_name, new_name in rename_map.items():
                    vg = mesh.vertex_groups.get(old_name)
                    if vg and not mesh.vertex_groups.get(new_name):
                        vg.name = new_name
                        vg_fixed += 1
            if vg_fixed > 0:
                print(f"[xps_to_mmd rename] VG 补正: {vg_fixed} 个 vertex group 重命名")

        bpy.context.object.data.show_names = True

        return {'FINISHED'}

    def rename_finger_bone(self, context, obj, scene, base_finger_name, segment):
        for side in ["left", "right"]:
            prop_name = f"{side}_{base_finger_name}_{segment}"
            if prop_name in self.mmd_bone_map:
                new_name = self.mmd_bone_map.get(prop_name)
                bone_name = getattr(scene, PREFIX + prop_name, None)
                if bone_name:
                    bone = obj.pose.bones.get(bone_name)
                    if bone:
                        # Check if the bone has already been renamed to the MMD format name
                        if bone.name != new_name:
                            bone.name = new_name
                            # Update the bone property value in the scene
                            setattr(scene, PREFIX + prop_name, new_name)
                        else:
                            self.report({'INFO'}, f"Bone '{bone_name}' is already renamed to {new_name}")
                    else:
                        self.report({'WARNING'}, f"Bone '{bone_name}' not found for renaming to {new_name}")


def register():
    bpy.utils.register_class(OBJECT_OT_rename_to_mmd)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_rename_to_mmd)


if __name__ == "__main__":
    register()
