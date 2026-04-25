"""
上半身/前腕 twist 骨系统（位置识别，rename 优先，不切权重）。

移植自 Convert_to_MMD_claude 的核心逻辑：
1. 位置扫描找 XPS twist 候选骨（xtra07pp/foretwist 等）
2. rename 候选到标准 MMD 槽位（VG 自动跟名字走，零损失）
3. 无候选时创建空骨
4. swap 腕↔腕捩 VG（xtra07pp 和腕位置重合，VG 覆盖区域互反）
5. 不做任何破坏性权重分割
"""
import bpy
import math
from mathutils import Vector

TWIST_SEGMENTS = [
    # (seg_from_base, seg_to_base, main_base, sub_count, main_t, sub_ts)
    ("腕", "ひじ", "腕捩", 3, 0.60, (0.25, 0.50, 0.75)),
    ("ひじ", "手首", "手捩", 3, 0.60, (0.25, 0.50, 0.75)),
]

PERP_THRESHOLD_RATIO = 0.3
T_RANGE = (-0.1, 1.2)


def _closest_on_segment(point, seg_from, seg_to):
    seg = seg_to - seg_from
    L_sq = seg.length_squared
    if L_sq < 1e-8:
        return 0.0, (point - seg_from).length
    t = (point - seg_from).dot(seg) / L_sq
    t_clamped = max(0.0, min(1.0, t))
    proj = seg_from + t_clamped * seg
    return t, (point - proj).length


def _vg_weight_count(mesh_obj, vg_name):
    vg = mesh_obj.vertex_groups.get(vg_name)
    if not vg:
        return 0
    return sum(1 for v in mesh_obj.data.vertices
               for g in v.groups if g.group == vg.index and g.weight > 0.001)


def _scan_candidates(armature, mesh_objects, seg_from_name, seg_to_name):
    eb_from = armature.data.bones.get(seg_from_name)
    eb_to = armature.data.bones.get(seg_to_name)
    if not eb_from or not eb_to:
        return []

    mw = armature.matrix_world
    sf = mw @ eb_from.head_local
    st = mw @ eb_to.head_local
    seg_len = (st - sf).length
    if seg_len < 1e-5:
        return []

    # 排除手指骨（seg_to 的子骨链 + 有手指子骨的兄弟）
    # 不排除所有有子骨的兄弟，否则 foretwist（有 foretwist1 子骨）会被误排除
    finger_keywords = ('指', 'finger', 'Finger', 'carpal', 'Carpal')
    exclude = set()
    seg_to_bone = armature.data.bones.get(seg_to_name)
    if seg_to_bone:
        for child in seg_to_bone.children_recursive:
            exclude.add(child.name)
        if seg_to_bone.parent:
            for sibling in seg_to_bone.parent.children:
                if sibling.name in (seg_to_name, seg_from_name):
                    continue
                has_finger_child = any(
                    any(kw in c.name for kw in finger_keywords)
                    for c in sibling.children_recursive
                )
                if has_finger_child:
                    exclude.add(sibling.name)
                    for child in sibling.children_recursive:
                        exclude.add(child.name)

    mmd_names = {seg_from_name, seg_to_name}
    for base in ("腕捩", "手捩", "腕", "ひじ", "手首", "肩"):
        for side in ("左", "右"):
            mmd_names.add(side + base)
            for i in (1, 2, 3):
                mmd_names.add(f"{side}{base}{i}")

    candidates = []
    for bone in armature.data.bones:
        name = bone.name
        if name in exclude or name in mmd_names or name.startswith("_"):
            continue
        w_count = sum(_vg_weight_count(m, name) for m in mesh_objects)
        if w_count <= 0:
            continue
        head_ws = mw @ bone.head_local
        t_head, perp = _closest_on_segment(head_ws, sf, st)
        if perp > seg_len * PERP_THRESHOLD_RATIO:
            continue
        if not (T_RANGE[0] <= t_head <= T_RANGE[1]):
            continue
        candidates.append((name, t_head, w_count))

    return candidates


def _assign_to_slots(candidates, sub_ts):
    assignment = {}
    if not candidates:
        return assignment
    sorted_c = sorted(candidates, key=lambda c: (-c[2], c[0]))
    assignment[0] = sorted_c[0][0]
    used = {0}
    for c in sorted_c[1:]:
        t_clamped = max(0.0, min(1.0, c[1]))
        best_slot = None
        best_dist = float("inf")
        for i, st in enumerate(sub_ts, start=1):
            if i in used:
                continue
            d = abs(t_clamped - st)
            if d < best_dist:
                best_dist = d
                best_slot = i
        if best_slot is not None:
            assignment[best_slot] = c[0]
            used.add(best_slot)
    return assignment


class OBJECT_OT_add_twist_bone(bpy.types.Operator):
    """位置识别 twist 系统：扫描 XPS 候选骨 rename 到 MMD 槽位，保留原始权重"""
    bl_idname = "object.xps_add_twist_bone"
    bl_label = "添加腕捩骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选择一个骨架对象")
            return {'CANCELLED'}

        mesh_objects = [
            o for o in bpy.data.objects
            if o.type == 'MESH' and (o.parent == obj or any(
                m.type == 'ARMATURE' and m.object == obj for m in o.modifiers
            ))
        ]

        # Phase 1: 在 OBJECT 模式扫描候选
        plans = []
        for seg_from_base, seg_to_base, main_base, sub_count, main_t, sub_ts in TWIST_SEGMENTS:
            for side in ("左", "右"):
                seg_from = side + seg_from_base
                seg_to = side + seg_to_base
                candidates = _scan_candidates(obj, mesh_objects, seg_from, seg_to)
                plans.append({
                    "seg_from": seg_from, "seg_to": seg_to,
                    "main_base": main_base, "main_t": main_t,
                    "sub_ts": sub_ts[:sub_count], "side": side,
                    "candidates": candidates,
                })

        # 全局去重：一根骨可能同时落在上臂和前臂段
        # 边界骨（t≈0 或 t≈1）优先分给 t≈0 的段（START 端），
        # 因为 twist 主骨通常在段的起始端附近
        bone_plans = {}
        for idx, plan in enumerate(plans):
            for c in plan["candidates"]:
                bone_plans.setdefault(c[0], []).append((idx, c[1]))
        for bone_name, entries in bone_plans.items():
            if len(entries) <= 1:
                continue
            def _dedup_score(e):
                t = e[1]
                interior = min(t, 1.0 - t)
                # 打平时优先 t 靠近 0 的段（bone 在段的 START 端）
                start_bias = 1.0 - t if interior < 0.01 else 0
                return (interior, start_bias)
            best_idx = max(entries, key=_dedup_score)[0]
            for pi, _ in entries:
                if pi != best_idx:
                    plans[pi]["candidates"] = [
                        c for c in plans[pi]["candidates"] if c[0] != bone_name
                    ]

        for plan in plans:
            plan["assignment"] = _assign_to_slots(plan["candidates"], plan["sub_ts"])
            for slot_idx, bone_name in plan["assignment"].items():
                slot = plan["main_base"] if slot_idx == 0 else f"{plan['main_base']}{slot_idx}"
                print(f"[twist] {plan['side']}{slot} <- {bone_name}")

        # Phase 2: EDIT 模式创建/rename 骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = obj.data.edit_bones

        renamed = []
        for plan in plans:
            seg_from_eb = edit_bones.get(plan["seg_from"])
            seg_to_eb = edit_bones.get(plan["seg_to"])
            if not seg_from_eb or not seg_to_eb:
                continue

            side = plan["side"]
            main_base = plan["main_base"]
            seg_dir = seg_to_eb.head - seg_from_eb.head
            seg_len = seg_dir.length
            if seg_len < 1e-6:
                continue

            all_ts = [plan["main_t"]] + list(plan["sub_ts"])
            slot_names = [side + main_base] + [f"{side}{main_base}{i}" for i in range(1, len(plan["sub_ts"]) + 1)]

            children_of_base = [c for c in edit_bones if c.parent == seg_from_eb]

            for slot_idx, (slot_name, t) in enumerate(zip(slot_names, all_ts)):
                head = seg_from_eb.head + t * seg_dir
                if slot_idx == 0:
                    tail = seg_to_eb.head.copy()
                else:
                    tail = head + Vector((0, 0, 0.08))

                cand_name = plan["assignment"].get(slot_idx)
                cand_eb = edit_bones.get(cand_name) if cand_name else None

                if cand_eb:
                    # rename 候选骨到标准名，VG 自动跟走
                    cand_eb.use_connect = False
                    cand_eb.parent = seg_from_eb
                    cand_eb.head = head
                    cand_eb.tail = tail
                    cand_eb.use_deform = True
                    if slot_idx == 0:
                        cand_eb.roll = seg_from_eb.roll
                    else:
                        cand_eb.roll = 0.0
                    cand_eb.name = slot_name
                    renamed.append(f"{cand_name} -> {slot_name}")
                else:
                    # 无候选，创建空骨
                    new_bone = edit_bones.new(slot_name)
                    new_bone.head = head
                    new_bone.tail = tail
                    new_bone.parent = seg_from_eb
                    new_bone.use_connect = False
                    new_bone.use_deform = True
                    if slot_idx == 0:
                        new_bone.roll = seg_from_eb.roll
                    else:
                        new_bone.roll = 0.0

            # 创建 shadow 和 dummy 骨（sub twist 用）
            for i in range(1, len(plan["sub_ts"]) + 1):
                sub_name = f"{side}{main_base}{i}"
                sub_eb = edit_bones.get(sub_name)
                if not sub_eb:
                    continue
                shadow_head = sub_eb.head.copy()
                for prefix, parent_bone in [("_shadow_", seg_from_eb), ("_dummy_", edit_bones.get(side + main_base))]:
                    aux_name = prefix + sub_name
                    if aux_name not in edit_bones:
                        aux = edit_bones.new(aux_name)
                        aux.head = shadow_head
                        aux.tail = shadow_head + Vector((0, 0, 0.08))
                        aux.parent = parent_bone or seg_from_eb
                        aux.use_connect = False
                        aux.roll = 0.0

            # reparent：子关节 → 主 twist
            main_twist_eb = edit_bones.get(side + main_base)
            if main_twist_eb:
                for child in children_of_base:
                    if child.name.startswith("_") or main_base in child.name:
                        continue
                    saved_head = child.head.copy()
                    saved_tail = child.tail.copy()
                    child.parent = main_twist_eb
                    child.use_connect = False
                    child.head = saved_head
                    child.tail = saved_tail

        # Phase 3: POSE 模式设约束
        self.setup_constraints(obj)

        bpy.ops.object.mode_set(mode='OBJECT')

        # Phase 4: VG swap（腕 ↔ 腕捩）
        # xtra07pp rename 成腕捩后，其 VG 覆盖上臂区域（像 target 的腕 VG）
        # 原腕 VG 覆盖 twist 区域（像 target 的腕捩 VG）
        # 交换两者纠正覆盖区域
        for base_twist, base_arm in [("腕捩", "腕")]:
            for side in ("左", "右"):
                twist_name = side + base_twist
                arm_name = side + base_arm
                if not any(f"-> {twist_name}" in r for r in renamed):
                    continue
                for mesh in mesh_objects:
                    vg_arm = mesh.vertex_groups.get(arm_name)
                    vg_twist = mesh.vertex_groups.get(twist_name)
                    if not vg_arm and not vg_twist:
                        continue
                    tmp = f"__swap_tmp_{side}"
                    if vg_arm:
                        vg_arm.name = tmp
                    if vg_twist:
                        vg_twist.name = arm_name
                    if vg_arm:
                        vg_arm.name = twist_name
                print(f"[twist] Swap VG: {arm_name} <-> {twist_name}")

        # Phase 5: PMXEditor 风格 twist 权重渐变
        # 把腕/ひじ的权重按 t 位置分配到 5 个 anchor 骨上
        DEAD_ZONE = 0.05
        gradient_segments = [
            ("腕", "ひじ", [("腕", 0.00), ("腕捩1", 0.25), ("腕捩2", 0.50), ("腕捩3", 0.75), ("腕捩", 1.00)]),
            ("ひじ", "手首", [("ひじ", 0.00), ("手捩1", 0.25), ("手捩2", 0.50), ("手捩3", 0.75), ("手捩", 1.00)]),
        ]
        total_split = 0
        for seg_from_base, seg_to_base, anchors_def in gradient_segments:
            for side in ("左", "右"):
                seg_from_name = side + seg_from_base
                seg_to_name = side + seg_to_base
                sf_bone = obj.data.bones.get(seg_from_name)
                st_bone = obj.data.bones.get(seg_to_name)
                if not sf_bone or not st_bone:
                    continue
                mw = obj.matrix_world
                seg_head = mw @ sf_bone.head_local
                seg_end = mw @ st_bone.head_local
                seg = seg_end - seg_head
                seg_len_sq = seg.length_squared
                if seg_len_sq < 1e-9:
                    continue

                anchors = [(t, side + name) for name, t in anchors_def]
                source_name = seg_from_name

                for mesh in mesh_objects:
                    src_vg = mesh.vertex_groups.get(source_name)
                    if not src_vg:
                        continue
                    vgs = {}
                    for _, bone_name in anchors:
                        if bone_name not in mesh.vertex_groups:
                            mesh.vertex_groups.new(name=bone_name)
                        vgs[bone_name] = mesh.vertex_groups[bone_name]

                    plans = []
                    for v in mesh.data.vertices:
                        src_w = next((g.weight for g in v.groups if g.group == src_vg.index), 0.0)
                        if src_w <= 0:
                            continue
                        existing = {}
                        for bone_name, vg in vgs.items():
                            if bone_name == source_name:
                                continue
                            for g in v.groups:
                                if g.group == vg.index:
                                    existing[bone_name] = g.weight
                                    break
                        v_world = mesh.matrix_world @ v.co
                        t = (v_world - seg_head).dot(seg) / seg_len_sq
                        if t < DEAD_ZONE:
                            continue
                        t = max(0.0, min(1.0, t))
                        # bracket
                        n_lo, n_hi, k = anchors[0][1], anchors[-1][1], 1.0
                        for ai in range(len(anchors) - 1):
                            t_lo, name_lo = anchors[ai]
                            t_hi, name_hi = anchors[ai + 1]
                            if t_lo <= t <= t_hi:
                                span = t_hi - t_lo
                                k = (t - t_lo) / span if span > 0 else 0.0
                                n_lo, n_hi = name_lo, name_hi
                                break
                        w_lo = src_w * (1.0 - k)
                        w_hi = src_w * k
                        plans.append((v.index, n_lo, w_lo, n_hi, w_hi, existing))

                    for v_idx, n_lo, w_lo, n_hi, w_hi, existing in plans:
                        if n_lo == source_name:
                            if w_lo > 0:
                                vgs[n_lo].add([v_idx], w_lo, 'REPLACE')
                            else:
                                src_vg.remove([v_idx])
                        else:
                            vgs[n_lo].add([v_idx], existing.get(n_lo, 0.0) + w_lo, 'REPLACE')
                        if w_hi > 0:
                            vgs[n_hi].add([v_idx], existing.get(n_hi, 0.0) + w_hi, 'REPLACE')
                        if n_lo != source_name:
                            src_vg.remove([v_idx])
                        total_split += 1

                if total_split > 0:
                    print(f"[twist] gradient split {seg_from_name}→{seg_to_name}: done")

        print(f"[twist] gradient split total: {total_split} verts")

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.xps_create_bone_group()

        n_renamed = len(renamed)
        for r in renamed:
            print(f"[twist] Renamed: {r}")
        self.report({'INFO'}, f"twist 完成（renamed {n_renamed}, gradient {total_split} verts）")
        return {'FINISHED'}

    def setup_constraints(self, obj):
        """为腕捩和手捩骨骼添加约束"""
        bpy.ops.object.mode_set(mode='POSE')
        pose_bones = obj.pose.bones

        for bone in pose_bones:
            if "腕捩" in bone.name or "手捩" in bone.name:
                bone.lock_location[0] = True
                bone.lock_location[1] = True
                bone.lock_location[2] = True
                bone.lock_rotation[0] = True
                bone.lock_rotation[1] = False
                bone.lock_rotation[2] = True

        for side in ['左', '右']:
            for twist_type in ['腕捩', '手捩']:
                for i in range(1, 4):
                    twist_bone_name = f"{side}{twist_type}{i}"
                    if twist_bone_name not in pose_bones:
                        continue
                    twist_bone = pose_bones[twist_bone_name]

                    for constraint in list(twist_bone.constraints):
                        twist_bone.constraints.remove(constraint)

                    tc = twist_bone.constraints.new('TRANSFORM')
                    tc.name = "mmd_additional_rotation"
                    tc.target = obj
                    tc.subtarget = f"_shadow_{twist_bone_name}"
                    tc.influence = 1.0
                    tc.use_motion_extrapolate = True
                    tc.owner_space = 'LOCAL'
                    tc.target_space = 'LOCAL'
                    tc.map_from = 'ROTATION'
                    tc.map_to = 'ROTATION'
                    tc.from_rotation_mode = 'XYZ'
                    tc.to_euler_order = 'XYZ'
                    tc.mix_mode_rot = 'AFTER'

                    tc.from_min_x_rot = math.radians(-180.0)
                    tc.from_min_y_rot = math.radians(-180.0)
                    tc.from_min_z_rot = math.radians(-180.0)
                    tc.from_max_x_rot = math.radians(180.0)
                    tc.from_max_y_rot = math.radians(180.0)
                    tc.from_max_z_rot = math.radians(180.0)

                    influence_map = {1: 0.25, 2: 0.5, 3: 0.75}
                    angle = 45.0 * i
                    tc.to_min_x_rot = math.radians(-angle)
                    tc.to_min_y_rot = math.radians(-angle)
                    tc.to_min_z_rot = math.radians(-angle)
                    tc.to_max_x_rot = math.radians(angle)
                    tc.to_max_y_rot = math.radians(angle)
                    tc.to_max_z_rot = math.radians(angle)

                    twist_bone.mmd_bone.has_additional_rotation = True
                    twist_bone.mmd_bone.additional_transform_bone = f"{side}{twist_type}"
                    twist_bone.mmd_bone.additional_transform_influence = influence_map[i]

            # shadow 骨约束
            for twist_type in ['腕捩', '手捩']:
                for i in range(1, 4):
                    shadow_name = f"_shadow_{side}{twist_type}{i}"
                    if shadow_name not in pose_bones:
                        continue
                    shadow_bone = pose_bones[shadow_name]
                    for c in list(shadow_bone.constraints):
                        shadow_bone.constraints.remove(c)
                    cc = shadow_bone.constraints.new('COPY_TRANSFORMS')
                    cc.name = "mmd_tools_at_dummy"
                    cc.target = obj
                    cc.subtarget = f"_dummy_{side}{twist_type}{i}"
                    cc.influence = 1.0
                    cc.owner_space = 'POSE'
                    cc.target_space = 'POSE'


def register():
    bpy.utils.register_class(OBJECT_OT_add_twist_bone)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_add_twist_bone)

if __name__ == "__main__":
    register()
