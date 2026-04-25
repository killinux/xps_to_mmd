"""XPS Lara 系专属修正 operator（从 Convert_to_MMD_claude 移植）。

5 个独立可选 operator，均不依赖参考 PMX，只用随包 canonical JSON：
- align_arms_to_canonical:  L1 rest pose 方向对齐
- align_fingers_to_canonical: L1 手指方向对齐
- fix_forearm_bend:         L1 前臂弯曲修正
- swap_twist_weights:       L3 结构化 VG 交换 (XPS Lara xtra07pp 陷阱)
- snap_misaligned_bones:    几何 snap 软组织骨到 vg 加权中心 (physics 前必跑)

不手动改单顶点权重 (R2)。不对 physics 参数做自动 loop (R17)。
"""
import bpy
import json
import math
import os
from mathutils import Matrix, Vector

from ..bone_utils import apply_armature_transforms


_CANON_ARM_CACHE = None
_CANON_FINGER_CACHE = None


def _load_canonical_arm_dirs():
    global _CANON_ARM_CACHE
    if _CANON_ARM_CACHE is not None:
        return _CANON_ARM_CACHE
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "presets", "canonical_arm_dirs.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = {}
        for side in ("L", "R"):
            arm = data["arms"][side]
            result[side] = (
                Vector(arm["upper_dir"]).normalized(),
                Vector(arm["fore_dir"]).normalized(),
            )
        _CANON_ARM_CACHE = result
        return result
    except Exception as e:
        print(f"[xps_fixes canonical-arm] 读取 {path} 失败: {e}")
        return None


def _load_canonical_finger_dirs():
    global _CANON_FINGER_CACHE
    if _CANON_FINGER_CACHE is not None:
        return _CANON_FINGER_CACHE
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "presets", "canonical_finger_dirs.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = {}
        for side in ("L", "R"):
            result[side] = {name: Vector(v).normalized() for name, v in data["fingers"][side].items()}
        _CANON_FINGER_CACHE = result
        return result
    except Exception as e:
        print(f"[xps_fixes canonical-finger] 读取 {path} 失败: {e}")
        return None


def _find_arm_chain(obj, side):
    """Return (shoulder, elbow, wrist) bone name tuple across common rig conventions, or None."""
    xps_side = "left" if side == "L" else "right"
    lr = "l" if side == "L" else "r"
    candidates = [
        # XNA Lara
        (f"arm {xps_side} shoulder 2", f"arm {xps_side} elbow", f"arm {xps_side} wrist"),
        # DAZ Genesis 8
        (f"{lr}ShldrBend", f"{lr}ForearmBend", f"{lr}Hand"),
        # Mixamo
        (f"mixamorig:{xps_side.capitalize()}Arm", f"mixamorig:{xps_side.capitalize()}ForeArm", f"mixamorig:{xps_side.capitalize()}Hand"),
        # VRM / Unity humanoid
        (f"Upper Arm.{side}", f"Lower Arm.{side}", f"Hand.{side}"),
        (f"UpperArm_{side}", f"LowerArm_{side}", f"Hand_{side}"),
        # MMD (post-rename)
        (f"腕.{side}", f"ひじ.{side}", f"手首.{side}"),
    ]
    bones = obj.data.bones
    for u, e, w in candidates:
        if u in bones and e in bones and w in bones:
            return u, e, w
    return None


def _bake_pose_delta_to_rest(context, obj, plans, log_tag):
    """Apply (bone_name, pivot_world, axis_world, angle_rad) rotations in pose mode
    then bake as rest pose. Mesh follows via duplicated armature modifier."""
    if not plans:
        return 'FINISHED'

    meshes_with_arm = []
    for m in bpy.data.objects:
        if m.type != 'MESH' or m.data.shape_keys:
            continue
        for mod in m.modifiers:
            if mod.type == 'ARMATURE' and mod.object == obj:
                meshes_with_arm.append(m)
                break

    created_temp = False
    if not meshes_with_arm:
        try:
            bpy.ops.mesh.primitive_cube_add(size=0.5)
            tmp = context.active_object
            tmp.name = "XPS_FIXES_TEMP_MESH"
            mod = tmp.modifiers.new(name="Armature", type='ARMATURE')
            mod.object = obj
            tmp["is_temp_mesh"] = True
            meshes_with_arm.append(tmp)
            created_temp = True
        except Exception as e:
            print(f"[{log_tag}] 创建临时网格失败: {e}")
            return 'CANCELLED'

    for m in meshes_with_arm:
        for mod in list(m.modifiers):
            if mod.type == 'ARMATURE' and mod.object == obj and "_copy" not in mod.name:
                new_mod = m.modifiers.new(name=mod.name + "_copy", type='ARMATURE')
                new_mod.object = mod.object
                new_mod.use_vertex_groups = mod.use_vertex_groups
                new_mod.use_bone_envelopes = mod.use_bone_envelopes
                break

    context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.rot_clear()
    bpy.ops.pose.scale_clear()
    bpy.ops.pose.loc_clear()
    bpy.ops.pose.select_all(action='DESELECT')

    for bone_name, pivot, axis, angle in plans:
        pb = obj.pose.bones[bone_name]
        rot_w = Matrix.Rotation(angle, 4, axis)
        delta = Matrix.Translation(pivot) @ rot_w @ Matrix.Translation(-pivot)
        pb.matrix = delta @ pb.matrix
        context.view_layer.update()

    try:
        for m in meshes_with_arm:
            context.view_layer.objects.active = m
            for mod in list(m.modifiers):
                if mod.type == 'ARMATURE' and mod.object == obj and "_copy" in mod.name:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    break
    except RuntimeError as e:
        for m in meshes_with_arm:
            for mod in list(m.modifiers):
                if "_copy" in mod.name:
                    m.modifiers.remove(mod)
        print(f"[{log_tag}] 应用 modifier 失败: {e}")
        return 'CANCELLED'

    context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='OBJECT')

    if created_temp:
        for m in meshes_with_arm:
            if m.get("is_temp_mesh"):
                bpy.data.objects.remove(m, do_unlink=True)

    return 'FINISHED'


# ============================================================
# 3a. Align arms to canonical
# ============================================================

class OBJECT_OT_align_arms_to_canonical(bpy.types.Operator):
    """L1 修正：把上臂 / 前腕方向对齐到标准 MMD A-pose canonical，烘焙到 rest pose。
    消除因 rest 方向与 target 差异导致的 VMD 回放手腕/指末漂移。"""
    bl_idname = "object.xps_align_arms_to_canonical"
    bl_label = "L1: 对齐上臂到 canonical"
    bl_description = "把上臂/前腕方向对齐到内置 MMD A-pose canonical，烘焙为新 rest pose"

    ANGLE_THRESHOLD_DEG = 0.5

    def _build_plan(self, obj, side, ref_upper_dir, ref_fore_dir):
        plans = []
        chain = _find_arm_chain(obj, side)
        if not chain:
            return plans
        u, e, w = chain
        conv_u = obj.data.bones[u].head_local.copy()
        conv_e = obj.data.bones[e].head_local.copy()
        conv_w = obj.data.bones[w].head_local.copy()

        dir_conv_upper = (conv_e - conv_u).normalized()
        upper_angle = dir_conv_upper.angle(ref_upper_dir)
        upper_axis = None
        upper_angle_valid = upper_angle >= math.radians(self.ANGLE_THRESHOLD_DEG)
        if upper_angle_valid:
            upper_axis = dir_conv_upper.cross(ref_upper_dir)
            if upper_axis.length < 1e-6:
                upper_angle_valid = False
            else:
                upper_axis.normalize()
                plans.append((u, conv_u.copy(), upper_axis, upper_angle))
                print(f"[xps_fixes align-arms] {side}: upper {u} 旋转 {math.degrees(upper_angle):.2f}°")

        if upper_angle_valid:
            R = Matrix.Rotation(upper_angle, 3, upper_axis)
            conv_e_new = conv_u + R @ (conv_e - conv_u)
            conv_w_new = conv_u + R @ (conv_w - conv_u)
        else:
            conv_e_new = conv_e
            conv_w_new = conv_w

        dir_conv_fore = (conv_w_new - conv_e_new).normalized()
        fore_angle = dir_conv_fore.angle(ref_fore_dir)
        if fore_angle >= math.radians(self.ANGLE_THRESHOLD_DEG):
            fore_axis = dir_conv_fore.cross(ref_fore_dir)
            if fore_axis.length > 1e-6:
                fore_axis.normalize()
                plans.append((e, conv_e_new.copy(), fore_axis, fore_angle))
                print(f"[xps_fixes align-arms] {side}: forearm {e} 旋转 {math.degrees(fore_angle):.2f}°")

        return plans

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}
        if not apply_armature_transforms(context):
            self.report({'ERROR'}, "apply_armature_transforms 失败")
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='OBJECT')

        canon = _load_canonical_arm_dirs()
        if not canon:
            self.report({'ERROR'}, "canonical_arm_dirs.json 读取失败")
            return {'CANCELLED'}

        all_plans = []
        for side in ("L", "R"):
            if side not in canon:
                continue
            ref_upper, ref_fore = canon[side]
            all_plans.extend(self._build_plan(obj, side, ref_upper, ref_fore))

        if not all_plans:
            self.report({'INFO'}, f"已接近 canonical (<{self.ANGLE_THRESHOLD_DEG}°)，无需修正")
            return {'FINISHED'}

        result = _bake_pose_delta_to_rest(context, obj, all_plans, "xps_fixes align-arms")
        if result != 'FINISHED':
            self.report({'ERROR'}, "烘焙到 rest pose 失败")
            return {'CANCELLED'}
        self.report({'INFO'}, f"上臂对齐完成 ({len(all_plans)} 处)")
        return {'FINISHED'}


# ============================================================
# 3b. Align fingers to canonical
# ============================================================

_FINGER_CHAINS = [
    ("親指０", "親指１", "親指２"),
    ("人指１", "人指２", "人指３"),
    ("中指１", "中指２", "中指３"),
    ("薬指１", "薬指２", "薬指３"),
    ("小指１", "小指２", "小指３"),
]


class OBJECT_OT_align_fingers_to_canonical(bpy.types.Operator):
    """L1 修正：把手指根段方向 (根骨 → 第1節) 对齐到 canonical。"""
    bl_idname = "object.xps_align_fingers_to_canonical"
    bl_label = "L1: 对齐手指到 canonical"
    bl_description = "把手指根段方向对齐到内置 canonical，烘焙为新 rest pose"

    ANGLE_THRESHOLD_DEG = 1.0

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}
        if not apply_armature_transforms(context):
            self.report({'ERROR'}, "apply_armature_transforms 失败")
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='OBJECT')

        canon = _load_canonical_finger_dirs()
        if not canon:
            self.report({'ERROR'}, "canonical_finger_dirs.json 读取失败")
            return {'CANCELLED'}

        plans = []
        for side in ("L", "R"):
            for chain in _FINGER_CHAINS:
                root_name = f"{chain[0]}.{side}"
                tip_name = f"{chain[1]}.{side}"
                conv_root = obj.data.bones.get(root_name)
                conv_tip = obj.data.bones.get(tip_name)
                if not conv_root or not conv_tip:
                    continue
                conv_dir = (conv_tip.head_local - conv_root.head_local)
                if conv_dir.length < 1e-6:
                    continue
                conv_dir = conv_dir.normalized()
                ref_dir = canon.get(side, {}).get(chain[0])
                if ref_dir is None:
                    continue
                angle = conv_dir.angle(ref_dir)
                if angle < math.radians(self.ANGLE_THRESHOLD_DEG):
                    continue
                axis = conv_dir.cross(ref_dir)
                if axis.length < 1e-6:
                    continue
                axis.normalize()
                pivot = conv_root.head_local.copy()
                plans.append((root_name, pivot, axis, angle))
                print(f"[xps_fixes align-fingers] {side}: {root_name} 旋转 {math.degrees(angle):.2f}°")

        if not plans:
            self.report({'INFO'}, "手指方向已接近 canonical，无需修正")
            return {'FINISHED'}

        result = _bake_pose_delta_to_rest(context, obj, plans, "xps_fixes align-fingers")
        if result != 'FINISHED':
            self.report({'ERROR'}, "烘焙到 rest pose 失败")
            return {'CANCELLED'}
        self.report({'INFO'}, f"手指对齐完成 ({len(plans)} 处)")
        return {'FINISHED'}


# ============================================================
# 3c. Fix forearm bend
# ============================================================

class OBJECT_OT_fix_forearm_bend(bpy.types.Operator):
    """L1 修正：把小手臂拉直到与上臂共线，然后烘焙到 rest pose。"""
    bl_idname = "object.xps_fix_forearm_bend"
    bl_label = "L1: 修正前腕弯曲"
    bl_description = "把小手臂拉直到与上臂共线，烘焙为新 rest pose"

    ANGLE_THRESHOLD_DEG = 2.0

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}
        if not apply_armature_transforms(context):
            self.report({'ERROR'}, "apply_armature_transforms 失败")
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='OBJECT')

        plans = []
        for side in ("L", "R"):
            chain = _find_arm_chain(obj, side)
            if not chain:
                continue
            u_name, e_name, w_name = chain
            u_head = obj.matrix_world @ obj.pose.bones[u_name].head
            e_head = obj.matrix_world @ obj.pose.bones[e_name].head
            w_head = obj.matrix_world @ obj.pose.bones[w_name].head
            upper_dir = (e_head - u_head).normalized()
            fore_dir = (w_head - e_head).normalized()
            if upper_dir.length == 0 or fore_dir.length == 0:
                continue
            angle = upper_dir.angle(fore_dir)
            if angle < math.radians(self.ANGLE_THRESHOLD_DEG):
                print(f"[xps_fixes fix-forearm] {side}: 已共线 ({math.degrees(angle):.2f}°)，跳过")
                continue
            axis = fore_dir.cross(upper_dir)
            if axis.length < 1e-6:
                continue
            axis.normalize()
            plans.append((e_name, e_head.copy(), axis, angle))
            print(f"[xps_fixes fix-forearm] {side}: {e_name} 旋转 {math.degrees(angle):.2f}° 拉直")

        if not plans:
            self.report({'INFO'}, "前腕已接近直线，无需修正")
            return {'FINISHED'}

        result = _bake_pose_delta_to_rest(context, obj, plans, "xps_fixes fix-forearm")
        if result != 'FINISHED':
            self.report({'ERROR'}, "烘焙到 rest pose 失败")
            return {'CANCELLED'}
        self.report({'INFO'}, f"前腕弯曲修正完成 ({len(plans)} 处)")
        return {'FINISHED'}


# ============================================================
# 3d. Swap twist weights (XPS Lara xtra07pp trap)
# ============================================================

class OBJECT_OT_swap_twist_weights(bpy.types.Operator):
    """L3 结构化权重交换（XPS Lara 专属陷阱）：

    XPS Lara 系源的 `arm xxx shoulder 2` 与 `xtra07pp` 位置重合，rename 到
    `腕.L` / `腕捩.L` 后 vertex group 实际覆盖区左右互反 —— 上臂顶点挂到
    捩骨、前臂顶点挂到腕 —— 动画完全跑飞。此 op 整组 VG 名互换来纠正。

    只交换 L/R 腕 ↔ 腕捩（上臂），手捩不触发（XPS 前臂 twist 辅助骨权重
    通常正确）。R2 合规：只动 VG 名，不碰单顶点权重。
    """
    bl_idname = "object.xps_swap_twist_weights"
    bl_label = "L3: XPS 捩骨权重交换"
    bl_description = "交换 腕 ↔ 腕捩 vertex group 名 (XPS Lara xtra07pp 陷阱)"

    OVERLAP_THRESHOLD_M = 0.02  # 腕 head 与 腕捩 head 距离 < 此值才视为 overlap

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}

        mesh_objects = [
            o for o in bpy.data.objects
            if o.type == 'MESH' and any(
                m.type == 'ARMATURE' and m.object == obj for m in o.modifiers
            )
        ]
        if not mesh_objects:
            self.report({'ERROR'}, "未找到挂此 armature 的 mesh")
            return {'CANCELLED'}

        swapped = 0
        skipped = []
        for side in ("L", "R"):
            arm_name = f"腕.{side}"
            twist_name = f"腕捩.{side}"
            arm_bone = obj.data.bones.get(arm_name)
            twist_bone = obj.data.bones.get(twist_name)
            if not arm_bone or not twist_bone:
                skipped.append(f"{side}:骨不存在")
                continue
            # 只在两根骨几乎重合时才 swap（overlap 判定）
            dist = (arm_bone.head_local - twist_bone.head_local).length
            if dist > self.OVERLAP_THRESHOLD_M:
                skipped.append(f"{side}:骨未重合(dist={dist:.3f}m)")
                print(f"[xps_fixes swap-twist] {side}: 腕↔腕捩 head 距离 {dist:.3f}m > {self.OVERLAP_THRESHOLD_M}m, 跳过")
                continue

            for mesh in mesh_objects:
                vg_arm = mesh.vertex_groups.get(arm_name)
                vg_twist = mesh.vertex_groups.get(twist_name)
                if not vg_arm and not vg_twist:
                    continue
                tmp_name = f"__xps_swap_tmp_{side}"
                if vg_arm:
                    vg_arm.name = tmp_name
                if vg_twist:
                    vg_twist.name = arm_name
                if vg_arm:
                    vg_arm.name = twist_name
            print(f"[xps_fixes swap-twist] {side}: Swap VG {arm_name} ↔ {twist_name}")
            swapped += 1

        if swapped == 0:
            msg = "未执行任何 swap: " + "; ".join(skipped)
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        self.report({'INFO'}, f"交换完成 {swapped} 侧 (跳过: {skipped})")
        return {'FINISHED'}


# ============================================================
# 3e. Snap misaligned bones (physics 前必跑)
# ============================================================

DEFAULT_SNAP_BONES = ('乳奶.L', '乳奶.R')


def _vg_weighted_center(arm_obj, bone_name, vg_name=None, weight_floor=0.5, top_n=80):
    """Top-N 高权重顶点的加权中心 (世界坐标)，返回 (center_world, n_verts)。"""
    vg_name = vg_name or bone_name
    candidates = []
    for me in bpy.data.objects:
        if me.type != 'MESH':
            continue
        uses_arm = False
        for mod in me.modifiers:
            if mod.type == 'ARMATURE' and mod.object is arm_obj:
                uses_arm = True
                break
        if not uses_arm and me.parent is not arm_obj:
            continue
        if vg_name not in me.vertex_groups:
            continue
        vg_idx = me.vertex_groups[vg_name].index
        for v in me.data.vertices:
            for g in v.groups:
                if g.group == vg_idx and g.weight >= weight_floor:
                    candidates.append((g.weight, me.matrix_world @ v.co))
                    break
    if not candidates:
        return None, 0
    candidates.sort(key=lambda x: -x[0])
    top = candidates[:top_n]
    center = sum((p for _, p in top), Vector((0, 0, 0))) / len(top)
    return center, len(top)


def snap_bone_to_vg_center(arm_obj, bone_name, threshold_m=0.05, vg_name=None, dry_run=False):
    """Snap `bone_name` head → vg 加权中心（tail 同步平移保持方向）。

    状态：'snapped' / 'aligned' / 'no-vg' / 'no-bone' / 'would-snap' (dry)
    """
    if bone_name not in arm_obj.data.bones:
        return {'bone': bone_name, 'status': 'no-bone'}
    center, n = _vg_weighted_center(arm_obj, bone_name, vg_name)
    if center is None:
        return {'bone': bone_name, 'status': 'no-vg'}
    head_world = arm_obj.matrix_world @ arm_obj.data.bones[bone_name].head_local
    delta = (center - head_world).length
    info = {
        'bone': bone_name,
        'head_old': tuple(round(v, 4) for v in head_world),
        'vg_center': tuple(round(v, 4) for v in center),
        'delta_m': round(delta, 4),
        'n_verts': n,
    }
    if delta < threshold_m:
        info['status'] = 'aligned'
        return info
    if dry_run:
        info['status'] = 'would-snap'
        return info

    arm_inv = arm_obj.matrix_world.inverted()
    center_local = arm_inv @ center
    head_local_old = arm_obj.data.bones[bone_name].head_local
    delta_local = center_local - head_local_old

    prev_active = bpy.context.view_layer.objects.active
    prev_hide = arm_obj.hide_viewport
    arm_obj.hide_viewport = False
    prev_selected = [o for o in bpy.context.view_layer.objects if o.select_get()]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        eb = arm_obj.data.edit_bones[bone_name]
        eb.head = eb.head + delta_local
        eb.tail = eb.tail + delta_local
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
        arm_obj.hide_viewport = prev_hide
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in prev_selected:
            try:
                o.select_set(True)
            except Exception:
                pass
        if prev_active is not None:
            bpy.context.view_layer.objects.active = prev_active

    head_new = arm_obj.matrix_world @ arm_obj.data.bones[bone_name].head_local
    info['head_new'] = tuple(round(v, 4) for v in head_new)
    info['status'] = 'snapped'
    return info


class OBJECT_OT_snap_misaligned_bones(bpy.types.Operator):
    """把位置错位的软组织骨（默认乳奶 L/R）snap 到 vg 加权中心。

    XPS 源常把乳奶/发根/挂饰锚放在解剖学错位 (Reika 乳奶 22cm)，不修则
    胸部/头发 rigid body 全绑错位。physics 前必跑。
    """
    bl_idname = "object.xps_snap_misaligned_bones"
    bl_label = "Snap 错位骨 (vg 中心)"
    bl_description = "软组织骨 (默认乳奶) snap 到 vg 加权中心"
    bl_options = {'REGISTER', 'UNDO'}

    bones_csv: bpy.props.StringProperty(
        name="Bones (csv)",
        description="逗号分隔骨名，留空走默认 (乳奶.L,乳奶.R)",
        default="",
    )
    threshold_cm: bpy.props.FloatProperty(
        name="Threshold (cm)",
        description="偏差小于此值不动",
        default=5.0, min=0.5, max=50.0,
    )
    dry_run: bpy.props.BoolProperty(
        name="Dry-run",
        description="只报告，不修改",
        default=False,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中 armature")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        bones = [b.strip() for b in self.bones_csv.split(',') if b.strip()] \
                if self.bones_csv else list(DEFAULT_SNAP_BONES)
        threshold_m = self.threshold_cm / 100.0

        snapped = []
        skipped = []
        for bn in bones:
            res = snap_bone_to_vg_center(obj, bn, threshold_m=threshold_m,
                                         dry_run=self.dry_run)
            tag = res.get('status', '?')
            if tag in ('snapped', 'would-snap'):
                snapped.append(res)
                print(f"[xps_fixes snap] {bn}: {tag}  delta={res.get('delta_m')}m  "
                      f"({res.get('n_verts')} verts)")
            else:
                skipped.append(res)
                print(f"[xps_fixes snap] {bn}: {tag}")

        if self.dry_run:
            self.report({'INFO'}, f"Dry-run: would-snap {len(snapped)} 骨; 跳过 {len(skipped)}")
        else:
            self.report({'INFO'}, f"Snap 完成: {len(snapped)} 骨; 跳过 {len(skipped)}")
        return {'FINISHED'}


_CLASSES = (
    OBJECT_OT_align_arms_to_canonical,
    OBJECT_OT_align_fingers_to_canonical,
    OBJECT_OT_fix_forearm_bend,
    OBJECT_OT_swap_twist_weights,
    OBJECT_OT_snap_misaligned_bones,
)


# ============================================================
# 3f. Transfer unused bone weights to nearest valid bone
# ============================================================

class OBJECT_OT_transfer_unused_weights(bpy.types.Operator):
    """把 unused 骨和非变形控制骨的权重转移到最近的有效变形骨。

    处理两类问题：
    1. unused 前缀骨 (XPS extra) — 跳过 foretwist 类
    2. 非变形控制骨有权重 (全ての親/センター/グルーブ) — 不应有 deform 权重
    """
    bl_idname = "object.xps_transfer_unused_weights"
    bl_label = "转移 unused 骨权重"
    bl_options = {'REGISTER', 'UNDO'}

    SKIP_PATTERNS = ('foretwist', 'pelvis', 'xtra08', 'xtra04', 'xtra02', 'xtra07', 'muscle')
    CONTROL_BONES = ('全ての親', 'センター', 'グルーブ')
    PELVIS_TO_LOWER = True

    def _auto_classify(self, armature):
        """Try auto-classification; returns dict or None on failure."""
        try:
            from ..skeleton_identifier import identify_skeleton, clear_cache
            from ..helper_classifier import classify_helpers
            clear_cache()
            smap = identify_skeleton(armature.data)
            if sum(1 for v in smap.values() if v) < 5:
                return None
            return classify_helpers(armature.data, smap)
        except Exception:
            return None

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}

        mesh_objects = [
            o for o in bpy.data.objects
            if o.type == 'MESH' and any(
                m.type == 'ARMATURE' and m.object == obj for m in o.modifiers
            )
        ]
        if not mesh_objects:
            self.report({'ERROR'}, "未找到挂此 armature 的 mesh")
            return {'CANCELLED'}

        cls = self._auto_classify(obj)

        if cls:
            unused_bones = [
                b for b in obj.data.bones
                if (cls.get(b.name) == 'other' and b.name.startswith('unused'))
                or cls.get(b.name) == 'merge'
            ]
            skipped = [
                b.name for b in obj.data.bones
                if cls.get(b.name) in ('twist', 'preserve')
            ]
            control_bones = [
                b for b in obj.data.bones
                if b.name in self.CONTROL_BONES
            ]
            print(f"\n[1.4 Transfer unused] 使用 auto-classifier")
        else:
            unused_bones = [
                b for b in obj.data.bones
                if b.name.startswith('unused')
                and not any(p in b.name.lower() for p in self.SKIP_PATTERNS)
            ]
            skipped = [
                b.name for b in obj.data.bones
                if b.name.startswith('unused')
                and any(p in b.name.lower() for p in self.SKIP_PATTERNS)
            ]
            control_bones = [
                b for b in obj.data.bones
                if b.name in self.CONTROL_BONES
            ]
            print(f"\n[1.4 Transfer unused] 使用硬编码 patterns (fallback)")

        bones_to_transfer = unused_bones + control_bones
        if skipped:
            print(f"  跳过 (twist/preserve): {skipped}")
        if unused_bones:
            print(f"  待转移 (unused): {[b.name for b in unused_bones]}")
        if control_bones:
            print(f"  待转移 (control): {[b.name for b in control_bones]}")
        if not bones_to_transfer:
            self.report({'INFO'}, "无需转移的骨骼")
            return {'FINISHED'}

        valid_deform_bones = [
            b for b in obj.data.bones
            if not b.name.startswith('unused')
            and not b.name.startswith('_shadow')
            and not b.name.startswith('_dummy')
            and b.use_deform
        ]
        if not valid_deform_bones:
            self.report({'ERROR'}, "无有效变形骨")
            return {'CANCELLED'}

        valid_heads = [(b, obj.matrix_world @ b.head_local) for b in valid_deform_bones]

        total_transferred = 0
        for mesh in mesh_objects:
            for ubone in bones_to_transfer:
                vg = mesh.vertex_groups.get(ubone.name)
                if not vg:
                    continue

                n = 0
                for v in mesh.data.vertices:
                    for g in v.groups:
                        if g.group == vg.index and g.weight > 0.001:
                            vert_pos = obj.matrix_world @ v.co
                            nearest = min(valid_heads, key=lambda bh: (bh[1] - vert_pos).length)[0]
                            tvg = mesh.vertex_groups.get(nearest.name)
                            if not tvg:
                                tvg = mesh.vertex_groups.new(name=nearest.name)
                            tvg.add([v.index], g.weight, 'ADD')
                            n += 1
                            break

                if n > 0:
                    print(f"[xps_fixes unused] {ubone.name} → per-vertex nearest: {n} verts")
                    total_transferred += n
                # Remove VG for unused or merged bones (transfer weights away).
                # Keep VG (just clear weights) for control bones (全ての親 etc.)
                # since they're standard MMD bones that should exist with no weight.
                if ubone.name.startswith('unused') or (cls and cls.get(ubone.name) == 'merge'):
                    mesh.vertex_groups.remove(vg)
                else:
                    vg.remove(list(range(len(mesh.data.vertices))))

        # pelvis 系骨直接映射到下半身（保留 XPS 原始权重）
        lower_body_bone = obj.data.bones.get('下半身')
        if lower_body_bone:
            if cls:
                pelvis_bone_names = [
                    b.name for b in obj.data.bones if cls.get(b.name) == 'pelvis'
                ]
            else:
                pelvis_bone_names = [
                    b.name for b in obj.data.bones
                    if b.name.startswith('unused') and 'pelvis' in b.name.lower()
                ]
            for mesh in mesh_objects:
                lb_vg = mesh.vertex_groups.get('下半身')
                if not lb_vg:
                    lb_vg = mesh.vertex_groups.new(name='下半身')
                for pname in pelvis_bone_names:
                    vg = mesh.vertex_groups.get(pname)
                    if not vg:
                        continue
                    n = 0
                    for v in mesh.data.vertices:
                        for g in v.groups:
                            if g.group == vg.index and g.weight > 0.001:
                                lb_vg.add([v.index], g.weight, 'ADD')
                                n += 1
                                break
                    if n > 0:
                        print(f"[xps_fixes] {pname} → 下半身 (direct): {n} verts")
                        total_transferred += n
                    mesh.vertex_groups.remove(vg)

        # 上半身/下半身 head 重合时的校正：
        # 上半身.head == 下半身.head，per-vertex-nearest 无法区分。
        # 把 上半身 VG 中位于 下半身 区域（z < 上半身.head.z）的顶点移到 下半身。
        lower_body = obj.data.bones.get('下半身')
        upper_body = obj.data.bones.get('上半身')
        if lower_body and upper_body:
            ub_z = (obj.matrix_world @ upper_body.head_local).z
            for mesh in mesh_objects:
                ub_vg = mesh.vertex_groups.get('上半身')
                lb_vg = mesh.vertex_groups.get('下半身')
                if not ub_vg:
                    continue
                if not lb_vg:
                    lb_vg = mesh.vertex_groups.new(name='下半身')
                moved = 0
                for v in mesh.data.vertices:
                    for g in v.groups:
                        if g.group == ub_vg.index and g.weight > 0.001:
                            vp = mesh.matrix_world @ v.co
                            if vp.z < ub_z - 0.01:
                                lb_vg.add([v.index], g.weight, 'ADD')
                                ub_vg.remove([v.index])
                                moved += 1
                            break
                if moved:
                    print(f"[xps_fixes] 上半身→下半身 (below spine): {moved} verts")
                    total_transferred += moved

        self.report({'INFO'}, f"转移 {total_transferred} 顶点权重")
        return {'FINISHED'}


_CLASSES = _CLASSES + (OBJECT_OT_transfer_unused_weights,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
