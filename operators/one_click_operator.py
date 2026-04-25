import bpy
import time


PIPELINE_STEPS = [
    ("0.5", "object.xps_correct_bones", "归正骨架位置", True),
    ("1", "object.xps_rename_to_mmd", "重命名为 MMD", True),
    ("1.4", "object.xps_transfer_unused_weights", "转移 unused 权重 (第一次)", False),
    ("1.5", "object.xps_fix_forearm_bend", "修正前腕弯曲", False),
    ("1.6", "object.xps_align_arms_to_canonical", "对齐上臂", False),
    ("1.7", "object.xps_align_fingers_to_canonical", "对齐手指", False),
    ("2", "object.xps_complete_missing_bones", "补全缺失骨骼", True),
    ("2.5", "object.xps_transfer_unused_weights", "清理控制骨权重 (第二次)", False),
    ("3", "object.xps_add_mmd_ik", "添加 MMD IK", True),
    ("4", "object.xps_create_bone_group", "创建骨骼集合", True),
    ("5", "object.xps_use_mmd_tools_convert", "mmd_tools 转换", True),
    ("6", "object.xps_add_leg_d_bones", "添加腿部 D 骨", False),
    ("7", "object.xps_add_twist_bone", "添加捩骨", False),
    ("8", "object.xps_add_shoulder_p_bones", "添加肩P骨", False),
]


def _find_armature():
    for o in bpy.data.objects:
        if o.type == 'ARMATURE' and 'backup' not in o.name.lower():
            return o
    return None


class OBJECT_OT_one_click_convert(bpy.types.Operator):
    """一键完成 XPS→MMD 全流程转换（自动识别 + 全部步骤）"""
    bl_idname = "object.xps_one_click_convert"
    bl_label = "一键转换 XPS→MMD"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        t_start = time.time()
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}

        results = []

        # Step 0: Auto identify
        try:
            bpy.ops.object.xps_auto_identify_skeleton()
            results.append(("0", "自动识别骨架", "OK"))
        except Exception as e:
            self.report({'ERROR'}, f"Step 0 自动识别失败: {e}")
            return {'CANCELLED'}

        # Run pipeline
        for step_num, op_id, label, critical in PIPELINE_STEPS:
            arm = _find_armature()
            if arm:
                context.view_layer.objects.active = arm
                arm.select_set(True)

            parts = op_id.split('.')
            op_func = getattr(getattr(bpy.ops, parts[0]), parts[1])

            try:
                t = time.time()
                result = op_func()
                dt = time.time() - t
                status = "OK" if result == {'FINISHED'} else str(result)
                results.append((step_num, label, f"{status} ({dt:.1f}s)"))
            except Exception as e:
                results.append((step_num, label, f"FAIL: {e}"))
                if critical:
                    self._print_summary(results, time.time() - t_start)
                    self.report({'ERROR'}, f"Step {step_num} {label} 失败: {e}")
                    return {'CANCELLED'}

        # apply_additional_transform
        try:
            bpy.ops.mmd_tools.apply_additional_transform()
            results.append(("8.5", "apply_additional_transform", "OK"))
        except Exception as e:
            results.append(("8.5", "apply_additional_transform", f"WARN: {e}"))

        total = time.time() - t_start
        self._print_summary(results, total)

        ok = sum(1 for _, _, s in results if s.startswith("OK"))
        self.report({'INFO'}, f"一键转换完成: {ok}/{len(results)} 步成功 ({total:.1f}s)")
        return {'FINISHED'}

    def _print_summary(self, results, total):
        print("\n" + "=" * 60)
        print("[xps_to_mmd] 一键转换结果")
        print("=" * 60)
        for step, label, status in results:
            mark = "✓" if status.startswith("OK") else ("⚠" if "WARN" in status else "✗")
            print(f"  {mark} Step {step:<5} {label:<28} {status}")
        print(f"\n  总耗时: {total:.1f}s")
        print("=" * 60)


def register():
    bpy.utils.register_class(OBJECT_OT_one_click_convert)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_one_click_convert)
