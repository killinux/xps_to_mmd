import bpy
import os
import json
from .properties import PREFIX

class OBJECT_OT_load_preset(bpy.types.Operator):
    bl_idname = "object.xps_load_preset"
    bl_label = "Load Preset"
    
    preset_name: bpy.props.StringProperty()
    
    def execute(self, context):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        presets_dir = os.path.join(script_dir, "presets")
        preset_path = os.path.join(presets_dir, f"{self.preset_name}.json")
        
        if os.path.exists(preset_path):
            with open(preset_path, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
                
            for prop_name, bone_name in preset_data.items():
                if hasattr(context.scene, PREFIX + prop_name):
                    setattr(context.scene, PREFIX + prop_name, bone_name)
        
        return {'FINISHED'}

def _add_bone_row(layout, scene, obj, label_text, prop_name):
    row = layout.row(align=True)
    split_name = row.split(factor=0.1, align=True)
    split_name.label(text=label_text)
    split_action = split_name.split(factor=1)
    sub_split = split_action.split(factor=(0.49*0.1), align=True)
    sub_split.operator(
        "object.xps_fill_from_selection_specific",
        text="",
        icon='ZOOM_SELECTED'
    ).bone_property = prop_name
    sub_split.prop_search(scene, PREFIX + prop_name, obj.data, "bones", text="")


def _add_symmetric_row(layout, scene, obj, label_text, left_prop, right_prop):
    row = layout.row(align=True)
    split_name = row.split(factor=0.1, align=True)
    split_name.label(text=label_text)
    split_action = split_name.split(factor=1, align=True)

    split_left_action = split_action.split(factor=0.49, align=True)
    col_left_action = split_left_action.column(align=True)
    row_left_action = col_left_action.row(align=True)
    sub_split_left_button = row_left_action.split(factor=0.1, align=True)
    sub_split_left_button.operator(
        "object.xps_fill_from_selection_specific", text="", icon='ZOOM_SELECTED'
    ).bone_property = left_prop
    sub_split_left_button.prop_search(scene, PREFIX + left_prop, obj.data, "bones", text="")

    split_divider = split_left_action.split(factor=(0.02/(0.02+0.49)), align=True)
    split_divider.label(text="|")

    split_right_action = split_divider.split(factor=1, align=True)
    col_right_action = split_right_action.column(align=True)
    row_right_action = col_right_action.row(align=True)
    sub_split_right_button = row_right_action.split(factor=0.1, align=True)
    sub_split_right_button.operator(
        "object.xps_fill_from_selection_specific", text="", icon='ZOOM_SELECTED'
    ).bone_property = right_prop
    sub_split_right_button.prop_search(scene, PREFIX + right_prop, obj.data, "bones", text="")


def _add_finger_row(layout, scene, obj, label_text, first_prop, second_prop, third_prop):
    divider_ratio = 0.02
    split_ratio = (1-2*divider_ratio)/3
    row = layout.row(align=True)
    split_name = row.split(factor=0.1, align=True)
    split_name.label(text=label_text)
    split_action = split_name.split(factor=1, align=True)

    split_first_action = split_action.split(factor=split_ratio, align=True)
    row_first = split_first_action.column(align=True).row(align=True)
    sub1 = row_first.split(factor=0.1, align=True)
    sub1.operator("object.xps_fill_from_selection_specific", text="", icon='ZOOM_SELECTED').bone_property = first_prop
    sub1.prop_search(scene, PREFIX + first_prop, obj.data, "bones", text="")

    split_d1 = split_first_action.split(factor=divider_ratio/(1-split_ratio), align=True)
    split_d1.label(text="|")

    split_second = split_d1.split(factor=split_ratio/(1-split_ratio-divider_ratio), align=True)
    row_second = split_second.column(align=True).row(align=True)
    sub2 = row_second.split(factor=0.1, align=True)
    sub2.operator("object.xps_fill_from_selection_specific", text="", icon='ZOOM_SELECTED').bone_property = second_prop
    sub2.prop_search(scene, PREFIX + second_prop, obj.data, "bones", text="")

    split_d2 = split_second.split(factor=divider_ratio/(1-split_ratio*2-divider_ratio), align=True)
    split_d2.label(text="|")

    split_third = split_d2.split(factor=1, align=True)
    row_third = split_third.column(align=True).row(align=True)
    sub3 = row_third.split(factor=0.1, align=True)
    sub3.operator("object.xps_fill_from_selection_specific", text="", icon='ZOOM_SELECTED').bone_property = third_prop
    sub3.prop_search(scene, PREFIX + third_prop, obj.data, "bones", text="")


class OBJECT_PT_skeleton_hierarchy(bpy.types.Panel):
    bl_label = "xps_to_mmd"
    bl_idname = "OBJECT_PT_xps_to_mmd"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "xps_to_mmd"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Step 0: Import XPS (始终顶部可见)
        row = layout.row()
        row.operator("object.xps_import_xps", text="0. 导入 XPS", icon='IMPORT')

        # 检查活动对象是否为骨架
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            layout.menu("TOPBAR_MT_file_import", text="Other Import", icon='IMPORT')
            return

        # 一键转换（最醒目位置）
        box = layout.box()
        box.operator("object.xps_one_click_convert", text="一键转换 XPS→MMD", icon='PLAY')

        # 添加选项卡按钮
        row = layout.row()
        row.prop(scene, "xps_my_enum", expand=True)
        if scene.xps_my_enum == 'option1':

            # 新增 EnumProperty 下拉菜单
            row = layout.row()
            row.prop(scene, "xps_preset_enum", text="")
            row.operator("object.xps_auto_identify_skeleton", text="Auto", icon='BONE_DATA')
            row.operator("object.xps_check_bones", text="Check", icon='VIEWZOOM')
        
            main_col = layout.column(align=True)
            # 全ての親到腰部分
            full_body_box = main_col.box()
            col = full_body_box.column()
            _add_bone_row(col, scene, obj, "操作中心", "control_center_bone")
            _add_bone_row(col, scene, obj, "全ての親", "all_parents_bone")
            _add_bone_row(col, scene, obj, "センター", "center_bone")
            _add_bone_row(col, scene, obj, "グルーブ", "groove_bone")
            _add_bone_row(col, scene, obj, "腰", "hip_bone")

            # 上半身到頭部分
            upper_body_box = main_col.box()
            col = upper_body_box.column()
            _add_bone_row(col, scene, obj, "上半身*", "upper_body_bone")
            _add_bone_row(col, scene, obj, "上半身2", "upper_body2_bone")
            _add_bone_row(col, scene, obj, "上半身3", "upper_body3_bone")
            _add_bone_row(col, scene, obj, "首*", "neck_bone")
            _add_bone_row(col, scene, obj, "頭*", "head_bone")
            _add_symmetric_row(col, scene, obj, "目", "left_eye_bone", "right_eye_bone")
            _add_symmetric_row(col, scene, obj, "肩*", "left_shoulder_bone", "right_shoulder_bone")
            _add_symmetric_row(col, scene, obj, "腕*", "left_upper_arm_bone", "right_upper_arm_bone")
            _add_symmetric_row(col, scene, obj, "ひじ*", "left_lower_arm_bone", "right_lower_arm_bone")
            _add_symmetric_row(col, scene, obj, "手首*", "left_hand_bone", "right_hand_bone")

            # 下半身到足首部分
            lower_body_box = main_col.box()
            col = lower_body_box.column()
            _add_bone_row(col, scene, obj, "下半身", "lower_body_bone")
            _add_symmetric_row(col, scene, obj, "足*", "left_thigh_bone", "right_thigh_bone")
            _add_symmetric_row(col, scene, obj, "ひざ*", "left_calf_bone", "right_calf_bone")
            _add_symmetric_row(col, scene, obj, "足首*", "left_foot_bone", "right_foot_bone")
            _add_symmetric_row(col, scene, obj, "足先EX", "left_toe_bone", "right_toe_bone")

            fingers_box = main_col.box()
            col = fingers_box.column()
            _add_finger_row(col, scene, obj, "左親指", "left_thumb_0", "left_thumb_1", "left_thumb_2")
            _add_finger_row(col, scene, obj, "左人指", "left_index_1", "left_index_2", "left_index_3")
            _add_finger_row(col, scene, obj, "左中指", "left_middle_1", "left_middle_2", "left_middle_3")
            _add_finger_row(col, scene, obj, "左薬指", "left_ring_1", "left_ring_2", "left_ring_3")
            _add_finger_row(col, scene, obj, "左小指", "left_pinky_1", "left_pinky_2", "left_pinky_3")

            _add_finger_row(col, scene, obj, "右親指", "right_thumb_0", "right_thumb_1", "right_thumb_2")
            _add_finger_row(col, scene, obj, "右人指", "right_index_1", "right_index_2", "right_index_3")
            _add_finger_row(col, scene, obj, "右中指", "right_middle_1", "right_middle_2", "right_middle_3")
            _add_finger_row(col, scene, obj, "右薬指", "right_ring_1", "right_ring_2", "right_ring_3")
            _add_finger_row(col, scene, obj, "右小指", "right_pinky_1", "right_pinky_2", "right_pinky_3")    
                
            # 添加导入/导出预设按钮
            row = layout.row()
            row.operator("object.xps_import_preset", text="导入预设")
            row.operator("object.xps_export_preset", text="导出预设")

            row = layout.row()
            # 添加T-Pose到A-Pose转换按钮
            row.operator("object.xps_convert_to_apose", text="转换为A-Pose")
            # 添加第 0 步归正骨骼按钮
            row.operator("object.xps_correct_bones", text="归正骨架位置")
            
            # 添加重命名按钮和补全缺失骨骼按钮到同一行
            row = layout.row()
            row.operator("object.xps_rename_to_mmd", text="1.重命名为MMD")
            row.operator("object.xps_complete_missing_bones", text="2.补全缺失骨骼")

            # 添加IK按钮和创建骨骼集合按钮到同一行
            row = layout.row()
            row.operator("object.xps_add_mmd_ik", text="3.添加MMD IK")
            row.operator("object.xps_create_bone_group", text="4.创建骨骼集合")

            # 添加“使用mmdtools转换格式”按钮到最下方
            layout.operator("object.xps_use_mmd_tools_convert", text="5.使用mmdtools转换格式")
        # 其他工具选项卡
        elif scene.xps_my_enum == 'option2':
            # 上部分：次标准骨骼
            secondary_bones_box = layout.box()
            secondary_bones_box.label(text="次标准骨骼", icon='BONE_DATA')
            
            # 添加合并足部骨骼链按钮
            row = secondary_bones_box.row()
            row.operator("object.xps_merge_leg_bones", text="1.合并足部骨骼链", icon='MOD_VERTEX_WEIGHT')
            # 添加腿部D骨骼按钮
            row = secondary_bones_box.row()
            row.operator("object.xps_add_leg_d_bones", text="2.添加腿部D骨骼", icon='BONE_DATA')
            # 添加合并手臂骨骼链按钮
            row = secondary_bones_box.row()
            row.operator("object.xps_merge_arm_bones", text="1.合并手臂骨骼链", icon='MOD_VERTEX_WEIGHT')
            #添加捩骨骼按钮
            row = secondary_bones_box.row()
            row.operator("object.xps_add_twist_bone", text="2.添加捩骨骼", icon='BONE_DATA')
            #添加肩P骨骼按钮
            row = secondary_bones_box.row()
            row.operator("object.xps_add_shoulder_p_bones", text="3.添加肩P骨骼", icon='BONE_DATA')
            
            # 物理：刚体 / 关节（先跑完主流水线第 5 步 + 必要 D 骨/捩骨再点）
            physics_box = layout.box()
            physics_box.label(text="物理 (先跑完主流水线第 5 步)", icon='PHYSICS')
            row = physics_box.row()
            row.operator("object.xps_generate_body_rigid_bodies", text="生成身体刚体", icon='MESH_CAPSULE')
            row = physics_box.row()
            row.operator("object.xps_generate_hair_physics", text="生成头发物理", icon='STRANDS')
            row = physics_box.row()
            row.operator("object.xps_generate_breast_physics", text="生成胸部物理", icon='META_BALL')

            # XPS Lara 专属修正（按 L1→L3 诊断顺序，按需使用）
            xps_fixes_box = layout.box()
            xps_fixes_box.label(text="XPS 专属修正 (L1→L3 诊断顺序)", icon='MODIFIER')
            xps_fixes_box.label(text="先查 L1 rest pose，再查 L2 约束，最后才动 L3 权重")
            row = xps_fixes_box.row()
            row.operator("object.xps_align_arms_to_canonical", text="L1: 对齐上臂")
            row.operator("object.xps_align_fingers_to_canonical", text="L1: 对齐手指")
            row = xps_fixes_box.row()
            row.operator("object.xps_fix_forearm_bend", text="L1: 修正前腕弯曲")
            row = xps_fixes_box.row()
            row.operator("object.xps_snap_misaligned_bones", text="Snap 错位骨 (physics 前必跑)")
            row = xps_fixes_box.row()
            row.operator("object.xps_swap_twist_weights", text="L3: XPS 捩骨权重交换 (Lara 专属)")

            # 下部分：通用工具
            general_tools_box = layout.box()
            general_tools_box.label(text="通用工具", icon='TOOL_SETTINGS')

            row = general_tools_box.row()
            row.operator("object.xps_clear_unweighted_bones", text="清理无权重骨骼", icon='X')
            # 添加导出骨骼信息按钮
            row = general_tools_box.row()
            row.operator("object.xps_export_selected_bones_info", text="导出所选骨骼信息", icon='EXPORT')
            # 添加导出骨骼约束关系按钮
            row = general_tools_box.row()
            row.operator("object.xps_export_selected_bones_constraints", text="导出所选骨骼约束关系", icon='EXPORT')

