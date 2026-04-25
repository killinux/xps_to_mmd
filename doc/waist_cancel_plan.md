# 添加 腰キャンセル.L/.R 骨骼到 pipeline

## Context

测试 Inase 时发现：auto-converted PMX 的 `右足D` parent 是 `下半身`，而目标 PMX 的 `足D.R` parent 是 `腰キャンセル.R`（中间多一层）。

`腰キャンセル`（waist cancel）是标准 MMD 骨骼，作用是**抵消腰部旋转**：当腰扭动时，腿不跟着扭。具体做法：
- parent = `下半身`
- additional_transform = `腰`，influence = **-1.0** （反向）
- 腿 (`左足`/`右足`) 和 D 骨 (`左足D`/`右足D`) 的 parent 改为 `腰キャンセル.L`/`.R`

我们 pipeline 缺这一层，导致腿 IK 在腰旋转时不能正确解耦。`Convert_to_MMD_claude` 已有现成参考实现（已通过 Inase + Reika 验证）。

最自然的添加位置是 `complete_bones_operator.py`，因为它已经在创建 下半身/足 等基础骨骼。

## 改动文件

### 1. `operators/complete_bones_operator.py` (主要改动)

**插入 腰キャンセル 骨创建** —— 在 `bone_properties` dict 中（约 line 235 之前，与 下半身 同级）添加：

```python
"腰キャンセル.L": {
    "head": edit_bones["左足"].head.copy(),
    "tail": edit_bones["左足"].head + Vector((0, 0, bone_length * 0.5)),
    "parent": "下半身",
    "use_connect": False,
    "use_deform": True
},
"腰キャンセル.R": {
    "head": edit_bones["右足"].head.copy(),
    "tail": edit_bones["右足"].head + Vector((0, 0, bone_length * 0.5)),
    "parent": "下半身",
    "use_connect": False,
    "use_deform": True
},
```

**修改 左足/右足 parent**（lines 239, 245）：
- `"左足"` parent: `"下半身"` → `"腰キャンセル.L"`
- `"右足"` parent: `"下半身"` → `"腰キャンセル.R"`

**在 OBJECT mode 设置 additional_transform**（在 `bone_utils.create_or_update_bone` 循环之后，切回 OBJECT 模式后添加）：

```python
# 腰キャンセル: 付与親=腰, influence=-1.0 (反転)
for side in (".L", ".R"):
    name = f"腰キャンセル{side}"
    pb = obj.pose.bones.get(name)
    if pb and obj.pose.bones.get("腰"):
        pb.mmd_bone.has_additional_rotation = True
        pb.mmd_bone.has_additional_location = False
        pb.mmd_bone.additional_transform_bone = "腰"
        pb.mmd_bone.additional_transform_influence = -1.0
        pb.mmd_bone.is_tip = True
    bone = obj.data.bones.get(name)
    if bone:
        bone.hide = True  # 控制骨，用户不直接操作
```

参考：`Convert_to_MMD_claude/operators/leg_operator.py:250-317` (创建)、`preset_operator.py:153-166` (付与親设置)

### 2. `operators/add_leg_d_bones_operator.py` (D骨 reparent)

**修改 D 骨的 parent**（lines 34, 50, 116, 132 等）：
- `"右足D"` parent: `"下半身"` → `"腰キャンセル.R"` (有 fallback)
- `"左足D"` parent: `"下半身"` → `"腰キャンセル.L"`
- `"_shadow_右足D"` parent: `"下半身"` → `"腰キャンセル.R"`
- `"_shadow_左足D"` parent: `"下半身"` → `"腰キャンセル.L"`

加一个 helper：
```python
hip_cancel_l = "腰キャンセル.L" if edit_bones.get("腰キャンセル.L") else "下半身"
hip_cancel_r = "腰キャンセル.R" if edit_bones.get("腰キャンセル.R") else "下半身"
```

### 3. `bone_map_and_group.py` (可选 — 加到骨集)

把 `腰キャンセル.L/.R` 加入"足"骨集（line 201-203 附近），便于在 Blender 中快速选择。

## 关键设计决策

**为何 additional_transform_bone="腰" 而不是"下半身"？**
- 反向 -1.0 抵消的是 *腰* 的旋转（祖父骨）
- 如果设为下半身（父），下半身大旋转会被叠加到腰キャンセル，导致腿 IK 剧烈抖动
- 来源：`Convert_to_MMD_claude/operators/preset_operator.py:153-156` 的踩坑注释

**为何用 `.L/.R` 后缀命名而非 `左/右` 前缀？**
- 腰キャンセル 是 MMD 后期添加的标准骨，约定使用 `.L/.R` 后缀（如目标 PMX、PMXEditor 默认）
- 我们其他骨用 `左/右` 前缀是历史习惯 — 混合命名在 MMD 是标准做法

**位置选取（与 左足/右足 head 重合）**：
- 腰キャンセル 是控制骨，无 mesh 权重
- head 与 足.head 重合 → tail 朝上 → 旋转中心和 足 一致
- 避免 mmd_tools 自动 dummy/shadow 系统出现位置错位

## 验证

按 `xps_to_mmd/doc/standard_test_procedure.md` 测试 Inase：

1. 跑完整 pipeline (auto-identify → ... → 补全骨骼 → ... → D骨)
2. 检查骨架结构：
   ```python
   arm.data.bones["腰キャンセル.L"].parent.name == "下半身"
   arm.data.bones["腰キャンセル.R"].parent.name == "下半身"
   arm.data.bones["左足"].parent.name == "腰キャンセル.L"
   arm.data.bones["右足D"].parent.name == "腰キャンセル.R"
   ```
3. 检查付与親：
   ```python
   pb = arm.pose.bones["腰キャンセル.R"]
   assert pb.mmd_bone.has_additional_rotation == True
   assert pb.mmd_bone.additional_transform_bone == "腰"
   assert pb.mmd_bone.additional_transform_influence == -1.0
   ```
4. 缩放到 21 单位 + 导出 PMX + 导入目标 + 加载 VMD
5. 在 frame 100-200（腰部转身的帧）观察：腿应该不跟着腰转
6. 对比目标 PMX 同帧效果：差异应消除

如果 `apply_additional_transform` 之后 PMX 重导入腰キャンセル 仍然丢失，需要检查 `is_tip` 和 use_deform 的设置（mmd_tools 对纯控制骨的导出规则）。

## 不在本次范围

- 不改其他模型（Reika 测试会作为后续验证）
- 不改 weights（腰キャンセル 不需要 vertex weights）
- 不改 ChainSetting/IK 配置
