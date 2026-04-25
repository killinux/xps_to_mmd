import bpy
from mathutils import Vector
from .. import bone_utils


def _split_chain_weights(obj, src_name, dst_name, seg_from_name, seg_to_name,
                         perp_threshold=1.5, src_keep_floor=0.0):
    """PMXEditor 风格两骨沿段 t ∈ [0,1] 线性插值权重分配。

    典型用法:
      - ("上半身2", "上半身3", "上半身2", "首"):  转移模式 (src_keep_floor=0.0)
    返回 (moved_verts, filtered_verts)。
    """
    src_keep_floor = max(0.0, min(1.0, src_keep_floor))
    src_b = obj.data.bones.get(seg_from_name)
    dst_b = obj.data.bones.get(seg_to_name)
    if not src_b or not dst_b:
        return (0, 0)
    seg_from = src_b.head_local
    seg_to = dst_b.head_local
    seg = seg_to - seg_from
    if seg.length_squared < 1e-9:
        return (0, 0)
    meshes = [
        m for m in bpy.data.objects
        if m.type == 'MESH' and any(
            mod.type == 'ARMATURE' and mod.object == obj for mod in m.modifiers
        )
    ]
    arm_mw = obj.matrix_world
    seg_from_w = arm_mw @ seg_from
    seg_to_w = arm_mw @ seg_to
    seg_w = seg_to_w - seg_from_w
    seg_len_sq_w = seg_w.length_squared
    if seg_len_sq_w < 1e-9:
        return (0, 0)
    perp_limit_sq = (perp_threshold * perp_threshold) * seg_len_sq_w
    moved = 0
    filtered = 0
    for m in meshes:
        src_vg = m.vertex_groups.get(src_name)
        if not src_vg:
            continue
        if dst_name not in m.vertex_groups:
            m.vertex_groups.new(name=dst_name)
        dst_vg = m.vertex_groups[dst_name]
        mesh_mw = m.matrix_world
        plans = []
        for v in m.data.vertices:
            src_w = 0.0
            existing_dst = 0.0
            for g in v.groups:
                if g.group == src_vg.index:
                    src_w = g.weight
                elif g.group == dst_vg.index:
                    existing_dst = g.weight
            if src_w <= 0:
                continue
            v_w = mesh_mw @ v.co
            rel = v_w - seg_from_w
            t = rel.dot(seg_w) / seg_len_sq_w
            t = max(0.0, min(1.0, t))
            if t <= 0:
                continue
            perp_sq = rel.length_squared - t * t * seg_len_sq_w
            if perp_sq > perp_limit_sq:
                filtered += 1
                continue
            k = t
            src_factor = 1.0 - k * (1.0 - src_keep_floor)
            new_src = src_w * src_factor
            new_dst = existing_dst + src_w * k
            plans.append((v.index, new_src, new_dst))
        for v_idx, new_src, new_dst in plans:
            if new_src > 1e-6:
                src_vg.add([v_idx], new_src, 'REPLACE')
            else:
                src_vg.remove([v_idx])
            if new_dst > 1e-6:
                dst_vg.add([v_idx], new_dst, 'REPLACE')
            moved += 1
    return (moved, filtered)


class OBJECT_OT_complete_missing_bones(bpy.types.Operator):
    """补充缺失的 MMD 格式骨骼"""
    bl_idname = "object.xps_complete_missing_bones"
    bl_label = "Complete Missing Bones"

    def connect_finger_bones(self, edit_bones):
        """连接手指骨骼的头尾"""
        # 定义手指骨骼链
        finger_chains = [
            # 左手手指
            ["左親指０", "左親指１", "左親指２"],
            ["左人指１", "左人指２", "左人指３"],
            ["左中指１", "左中指２", "左中指３"],
            ["左薬指１", "左薬指２", "左薬指３"],
            ["左小指１", "左小指２", "左小指３"],
            # 右手手指
            ["右親指０", "右親指１", "右親指２"],
            ["右人指１", "右人指２", "右人指３"],
            ["右中指１", "右中指２", "右中指３"],
            ["右薬指１", "右薬指２", "右薬指３"],
            ["右小指１", "右小指２", "右小指３"]
        ]
        
        # 连接每个手指骨骼链
        for chain in finger_chains:
            # 检查链中的所有骨骼是否都存在
            if all(bone in edit_bones for bone in chain):
                # 依次连接手指骨骼的头尾
                for i in range(len(chain) - 1):
                    current_bone = edit_bones[chain[i]]
                    next_bone = edit_bones[chain[i + 1]]
                    # 将当前骨骼的尾部设置为下一个骨骼的头部
                    current_bone.tail = next_bone.head

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "没有选择骨架")
            return {'CANCELLED'}

        # 确保当前处于编辑模式 (EDIT mode)
        if context.mode != 'EDIT_ARMATURE':
            bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = obj.data.edit_bones
        # 获取需要修改的骨骼
        left_foot_bone = edit_bones.get("左足")
        right_foot_bone = edit_bones.get("右足")
        upper_body_bone = edit_bones.get("上半身")
        lower_body_bone = edit_bones.get("下半身")
        # 清除 左足 和 右足 骨骼的父级
        if left_foot_bone:
            left_foot_bone.use_connect = False
            left_foot_bone.parent = None
        if right_foot_bone:
            right_foot_bone.use_connect = False
            right_foot_bone.parent = None
        # 清除 上半身 骨骼的父级
        if upper_body_bone and upper_body_bone.parent:
            upper_body_bone.use_connect = False
            upper_body_bone.parent = None
        # 清除 下半身 骨骼的父级
        if lower_body_bone and lower_body_bone.parent:
            lower_body_bone.use_connect = False
            lower_body_bone.parent = None
        # 确认上半身骨骼存在
        if not upper_body_bone:
            self.report({'ERROR'}, "上半身骨骼不存在")
            return {'CANCELLED'}
        # 获取 上半身 骨骼的坐标
        upper_body_head = upper_body_bone.head.copy()
        upper_body_tail = upper_body_bone.tail.copy()
        
        # 计算骨架高度和bone_length
        bone_length = bone_utils.calculate_bone_length(edit_bones) 

        # 定义基本骨骼的属性
        bone_properties = {

            "全ての親": {"head": Vector((0, 0, 0)), "tail": Vector((0, 0, bone_length)), "parent": None, "use_deform": False, "use_connect": False},
            "センター": {"head": Vector((0, 0, bone_length * 2)), "tail": Vector((0, 0, bone_length*1.1)), "parent": "全ての親", "use_deform": False, "use_connect": False},
            "グルーブ": {"head": Vector((0, 0, bone_length * 3.2)), "tail": Vector((0, 0, bone_length * 4)), "parent": "センター", "use_deform": False, "use_connect": False},
            "腰": {"head": Vector((0, upper_body_head.y + bone_length * 0.5, upper_body_head.z - bone_length * 0.5)), "tail": Vector((0, upper_body_head.y, upper_body_head.z)), 
                "parent": "グルーブ", "use_deform": False, "use_connect": False},
            "上半身": {"head": Vector((0, upper_body_head.y, upper_body_head.z)),
                "tail": Vector((0, upper_body_tail.y, upper_body_head.z+bone_length)), 
                "parent": "腰", "use_connect": False},
            "首": {
                "head": edit_bones["首"].head,
                "tail": edit_bones["頭"].head,
                "parent": "上半身2" if edit_bones.get("上半身2") else "上半身",
                "use_connect": False
            },
            "頭": {
                "head": edit_bones["頭"].head,
                "tail": Vector((0, edit_bones["頭"].head.y - bone_length * 0.3, edit_bones["頭"].head.z)),
                "parent": "首",
                "use_connect": False
            },                                  
            # 上肢骨骼链
            "左肩": {
                "head": edit_bones["左肩"].head,
                "tail": edit_bones["左腕"].head,
                "parent": edit_bones["左肩"].parent.name if edit_bones["左肩"].parent else None,
                "use_connect": False
            },
            "左腕": {
                "head": edit_bones["左腕"].head,
                "tail": edit_bones["左ひじ"].head,
                "parent": "左肩",
                "use_connect": True
            },
            "左ひじ": {
                "head": edit_bones["左ひじ"].head,
                "tail": edit_bones["左手首"].head if edit_bones["左手首"]else edit_bones["左ひじ"].tail,
                "parent": "左腕",
                "use_connect": True
            },
            "左手首": {
                "head": edit_bones["左手首"].head,
                "tail": edit_bones["左中指１"].head.copy() if edit_bones.get("左中指１") else edit_bones["左手首"].tail,
                "parent": "左ひじ",
                "use_connect": True
            },

            "右肩": {
                "head": edit_bones["右肩"].head,
                "tail": edit_bones["右腕"].head,
                "parent": edit_bones["右肩"].parent.name if edit_bones["右肩"].parent else None,
                "use_connect": False
            },
            "右腕": {
                "head": edit_bones["右腕"].head,
                "tail": edit_bones["右ひじ"].head,
                "parent": "右肩",
                "use_connect": True
            },
            "右ひじ": {
                "head": edit_bones["右ひじ"].head,
                "tail": edit_bones["右手首"].head if edit_bones["右手首"]else edit_bones["右ひじ"].tail,
                "parent": "右腕",
                "use_connect": True
            },
            "右手首": {
                "head": edit_bones["右手首"].head,
                "tail": edit_bones["右中指１"].head.copy() if edit_bones.get("右中指１") else edit_bones["右手首"].tail,
                "parent": "右ひじ",
                "use_connect": True
            },

            "下半身": {"head": Vector((0, upper_body_head.y, upper_body_head.z)), "tail": Vector((0, upper_body_head.y, upper_body_head.z - bone_length)), "parent": "腰", "use_connect": False},
            "左足": {
                "head": edit_bones["左足"].head,
                "tail": edit_bones["左ひざ"].head,
                "parent": "下半身",
                "use_connect": False
            },
            "右足": {
                "head": edit_bones["右足"].head,
                "tail": edit_bones["右ひざ"].head,
                "parent": "下半身",
                "use_connect": False
            },
            "左ひざ": {
                "head": edit_bones["左ひざ"].head,
                "tail": edit_bones["左足首"].head,
                "parent": "左足",
                "use_connect": False
            },
            "右ひざ": {
                "head": edit_bones["右ひざ"].head,
                "tail": edit_bones["右足首"].head,
                "parent": "右足",
                "use_connect": False
            },
            "左足首": {
                "head": edit_bones["左足首"].head,
                "tail": Vector((edit_bones["左足首"].head.x, edit_bones["左足首"].head.y - bone_length*0.3, 0)),
                "parent": "左ひざ",
                "use_connect": False
            },
            "右足首": {
                "head": edit_bones["右足首"].head,
                "tail": Vector((edit_bones["右足首"].head.x, edit_bones["右足首"].head.y - bone_length*0.3, 0)),
                "parent": "右ひざ",
                "use_connect": False
            },
            "左足先EX": {
                "head": edit_bones["左足首"].tail,
                "tail": Vector((edit_bones["左足首"].tail.x, edit_bones["左足首"].tail.y - bone_length*0.5, 0)),
                "parent": "左足首",
                "use_connect": False
            },
            "右足先EX": {
                "head": edit_bones["右足首"].tail,
                "tail": Vector((edit_bones["右足首"].tail.x, edit_bones["右足首"].tail.y - bone_length*0.5, 0)),
                "parent": "右足首",
                "use_connect": False
            }            
        }

        # 检查上半身2骨骼是否存在，如果存在则添加到属性字典
        if edit_bones.get("上半身2"):
            bone_properties["上半身2"] = {
                "head": Vector((0, edit_bones["上半身2"].head.y, edit_bones["上半身2"].head.z)),
                "tail": Vector((0, edit_bones["首"].head.y, edit_bones["首"].head.z)),
                "parent": "上半身", "use_connect": False
            }

        # 上半身3 自动补全 (坑 1 + 坑 3 的 VMD 语义必需骨):
        #   VMD 标准规格包含上半身3 keyframe，缺此骨 → 上半身僵硬。
        #   target PMX 实测约 10900 verts 挂在上半身3，腋窝顶点几乎全部
        #   同时挂 肩+腕+上半身3。
        # 逻辑:
        #   - 只在 上半身2 + 首 都存在，且上半身3 当前不存在时创建
        #   - 上半身2.tail 改为 (上半身2.head → 首.head) 中点，让出位置
        #   - 上半身3: head = 中点, tail = 首.head, parent = 上半身2
        #   - 首.parent 从 上半身2 改为 上半身3
        #   - 创建后进行权重沿段 t 线性迁移 (上半身2 → 上半身3)
        upper3_just_created = False
        if (edit_bones.get("上半身2") and edit_bones.get("首")
                and not edit_bones.get("上半身3")):
            upper2_head = bone_properties["上半身2"]["head"].copy()
            neck_head = bone_properties["首"]["head"].copy()
            spine_split_mid = (upper2_head + neck_head) * 0.5
            # 只在 上半身2 和 首 间距足够时才拆（避免零长骨）
            if (neck_head - upper2_head).length > bone_length * 0.2:
                # 缩短上半身2 tail 到中点
                bone_properties["上半身2"]["tail"] = spine_split_mid.copy()
                # 插入 上半身3
                bone_properties["上半身3"] = {
                    "head": spine_split_mid.copy(),
                    "tail": Vector((neck_head.x, neck_head.y, neck_head.z)),
                    "parent": "上半身2", "use_connect": False, "use_deform": True,
                }
                # 首 parent 指向 上半身3
                bone_properties["首"]["parent"] = "上半身3"
                upper3_just_created = True

        # 按顺序检查并创建或更新骨骼
        for bone_name, properties in bone_properties.items():
            # 如果是足先EX且已经存在，保持其头位置不变
            if bone_name in ["左足先EX", "右足先EX"] and bone_name in edit_bones:
                # 保持原有的头位置，只更新尾部和其他属性
                original_head = edit_bones[bone_name].head.copy()
                bone_utils.create_or_update_bone(edit_bones, bone_name, original_head, properties["tail"], properties.get("use_connect", False), properties["parent"], properties.get("use_deform", True))
            else:
                # 正常创建或更新骨骼
                bone_utils.create_or_update_bone(edit_bones, bone_name, properties["head"], properties["tail"], properties.get("use_connect", False), properties["parent"], properties.get("use_deform", True))
        
        # 如果存在足先EX骨骼，将足首的尾部指向足先EX的头部
        if "左足先EX" in edit_bones:
            # 更新左足首的尾部到左足先EX的头部
            edit_bones["左足首"].tail = edit_bones["左足先EX"].head
        if "右足先EX" in edit_bones:
            # 更新右足首的尾部到右足先EX的头部
            edit_bones["右足首"].tail = edit_bones["右足先EX"].head


        # 二次 pass 修复 parent 依赖顺序问题
        # (首 在 dict 中先于 上半身3，create_or_update_bone 时 上半身3 还不存在)
        for bone_name, properties in bone_properties.items():
            parent_name = properties.get("parent")
            if parent_name and bone_name in edit_bones:
                parent_bone = edit_bones.get(parent_name)
                if parent_bone and edit_bones[bone_name].parent != parent_bone:
                    edit_bones[bone_name].parent = parent_bone

        # unused bip001 pelvis → reparent to 下半身
        # XPS pelvis helper 骨 (xtra08 等) parent 在 pelvis→センター 链上，
        # 需要挂到 下半身 才能跟随下半身旋转
        pelvis_bone = edit_bones.get("unused bip001 pelvis")
        lower_body = edit_bones.get("下半身")
        if pelvis_bone and lower_body:
            pelvis_bone.parent = lower_body

        # 调用函数设置 roll 値
        bone_utils.set_roll_values(edit_bones, bone_utils.DEFAULT_ROLL_VALUES)

        # 连接手指骨骼的头尾
        self.connect_finger_bones(edit_bones)

        # 上半身3 自动权重分割 (仅当本次自动创建时触发)
        # 回到 OBJECT mode 才能改 vertex group
        if upper3_just_created:
            bpy.ops.object.mode_set(mode='OBJECT')
            try:
                moved, filtered = _split_chain_weights(
                    obj, "上半身2", "上半身3", "上半身2", "首"
                )
                print(f"[xps_to_mmd complete_bones] 上半身3 auto-weight: "
                      f"{moved} verts split from 上半身2, {filtered} filtered by perp")
                self.report(
                    {'INFO'},
                    f"上半身3 已补齐，{moved} 顶点权重从 上半身2 分配过来",
                )
            except Exception as e:
                print(f"[xps_to_mmd complete_bones] 上半身3 权重分割失败: {e}")
                self.report({'WARNING'}, f"上半身3 权重分割失败: {e}")
            bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


def register():
    bpy.utils.register_class(OBJECT_OT_complete_missing_bones)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_complete_missing_bones)


if __name__ == "__main__":
    register()
