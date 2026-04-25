"""Operator: check bone state — print unmatched bones, orphan VGs, classification summary.

Use this to manually review the armature before proceeding with the pipeline.
"""

import bpy
from collections import Counter

from ..properties import PREFIX
from ..bone_map_and_group import mmd_bone_map
from ..skeleton_identifier import identify_skeleton, clear_cache
from ..helper_classifier import classify_helpers


class OBJECT_OT_check_bones(bpy.types.Operator):
    """检查骨骼状态：未匹配的 MMD 槽位、可疑权重、分类汇总（输出到 console log）"""
    bl_idname = "object.xps_check_bones"
    bl_label = "Check Bones"

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "未选择骨架对象")
            return {'CANCELLED'}

        scene = context.scene
        bones = obj.data.bones
        bone_names = set(b.name for b in bones)
        meshes = [
            o for o in bpy.data.objects
            if o.type == 'MESH' and any(
                m.type == 'ARMATURE' and m.object == obj for m in o.modifiers
            )
        ]

        clear_cache()
        smap = identify_skeleton(obj.data)
        cls = classify_helpers(obj.data, smap)

        print("\n" + "=" * 60)
        print(f"[Check Bones] {obj.name} ({len(bones)} bones, {len(meshes)} meshes)")
        print("=" * 60)

        # 1. MMD slot fills (from scene properties)
        unfilled_slots = []
        filled_slots = []
        for prop_name, mmd_name in mmd_bone_map.items():
            xps_name = getattr(scene, PREFIX + prop_name, "")
            if xps_name:
                in_arm = xps_name in bone_names
                filled_slots.append((mmd_name, xps_name, in_arm))
            else:
                unfilled_slots.append((mmd_name, prop_name))

        if unfilled_slots:
            print(f"\n--- 未填充的 MMD 槽位 ({len(unfilled_slots)}) ---")
            for mmd_name, prop in unfilled_slots:
                print(f"  {mmd_name:10s}  ({prop})")

        broken_fills = [(m, x) for m, x, in_arm in filled_slots if not in_arm]
        if broken_fills:
            print(f"\n--- ⚠ 槽位指向不存在的骨骼 ({len(broken_fills)}) ---")
            for mmd_name, xps_name in broken_fills:
                print(f"  {mmd_name:10s} ← '{xps_name}' (不存在)")

        # 2. Helper classification
        counts = Counter(cls.values())
        print(f"\n--- Helper 骨分类汇总 ---")
        for cat in ("mapped", "twist", "pelvis", "preserve", "merge", "ignore", "other"):
            n = counts.get(cat, 0)
            if n:
                names = sorted([k for k, v in cls.items() if v == cat])
                preview = ", ".join(names[:5])
                if len(names) > 5:
                    preview += f" ... (+{len(names) - 5})"
                print(f"  {cat:10s} {n:3d}  {preview}")

        # 3. Bones with weights — categorize by status
        weighted_bones = {}  # bone_name -> total verts
        for mesh in meshes:
            for vg in mesh.vertex_groups:
                n = sum(1 for v in mesh.data.vertices
                        for g in v.groups if g.group == vg.index and g.weight > 0.001)
                if n > 0:
                    weighted_bones[vg.name] = weighted_bones.get(vg.name, 0) + n

        # 4. Orphan VGs (have weights but no matching bone)
        orphan = []
        for vg_name, count in weighted_bones.items():
            if vg_name not in bone_names:
                orphan.append((vg_name, count))

        if orphan:
            print(f"\n--- ⚠ 孤儿 VG (有权重但无骨骼，PMX 导出会丢失) ({len(orphan)}) ---")
            for name, count in sorted(orphan, key=lambda x: -x[1]):
                print(f"  {name:35s}  {count:5d} verts")

        # 5. Suspicious weighted bones — non-mapped, non-MMD, non-classified-helper
        suspicious = []
        mmd_chars = set('上半下首頭腕足肩捩ＩＫ親指人中薬小目腰グルセン全肘膝')
        # Bones with weights
        for bone_name, count in weighted_bones.items():
            if bone_name not in bone_names:
                continue  # already in orphan
            # Skip dummy/shadow
            if bone_name.startswith(('_dummy_', '_shadow_')):
                continue
            # Skip MMD-named bones (contain CJK chars)
            if any(c in mmd_chars for c in bone_name):
                continue
            # Skip if mapped or classified as preserve/twist/pelvis (intentional)
            cat = cls.get(bone_name, "")
            if cat in ("mapped", "twist", "pelvis", "preserve"):
                continue
            suspicious.append((bone_name, count, cat or "?"))

        if suspicious:
            print(f"\n--- ⚠ 可疑权重骨 (XPS 原名 + 非保留分类，可能需手动处理) ({len(suspicious)}) ---")
            for name, count, cat in sorted(suspicious, key=lambda x: -x[1]):
                print(f"  [{cat:7s}] {name:35s}  {count:5d} verts")

        # 6. Bones in armature with NO weights (potentially deletable)
        no_weight_bones = []
        for b in bones:
            if b.name.startswith(('_dummy_', '_shadow_')):
                continue
            if b.name not in weighted_bones:
                no_weight_bones.append(b.name)

        # Show only the suspicious no-weight ones (non-MMD, non-control, non-IK)
        suspicious_no_weight = [
            n for n in no_weight_bones
            if not any(c in mmd_chars for c in n)
            and cls.get(n, "") not in ("mapped",)
        ]
        if suspicious_no_weight:
            print(f"\n--- 提示：无权重的 XPS 骨骼 ({len(suspicious_no_weight)}) ---")
            for name in suspicious_no_weight[:20]:
                cat = cls.get(name, "?")
                print(f"  [{cat:7s}] {name}")
            if len(suspicious_no_weight) > 20:
                print(f"  ... +{len(suspicious_no_weight) - 20} more")

        print("=" * 60)

        # Summary report
        n_susp = len(suspicious)
        n_orphan = len(orphan)
        n_unfilled = len(unfilled_slots)
        n_broken = len(broken_fills)

        if n_susp == 0 and n_orphan == 0 and n_broken == 0:
            self.report({'INFO'}, f"检查通过：未匹配槽位 {n_unfilled}，无可疑骨骼")
        else:
            self.report(
                {'WARNING'},
                f"检查发现：可疑 {n_susp}，孤儿 VG {n_orphan}，broken {n_broken} (详见 console)"
            )

        return {'FINISHED'}


def register():
    bpy.utils.register_class(OBJECT_OT_check_bones)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_check_bones)
