# XPS→PMX 腰/臀/大腿 权重踩坑全记录

> 从 Convert_to_MMD_claude 12 轮 + xps_to_mmd 36+ 轮迭代提炼。
> 最后更新: 2026-04-25 (pelvis VG 时序 bug 修复后)

---

## 一句话总结

**不切权重，不合 helper，不跳诊断层级。** 腰/臀/大腿 90% 的"权重问题"根因在骨骼结构（parent 链、控制骨缺失、rest pose 没对齐），不在权重本身。

---

## 正确的 Pipeline 执行路径

下面是经过验证的正确顺序，每一步的位置都不能挪：

```
Step 0    auto_identify_skeleton     → 骨架自动识别 + helper 分类
Step 0.5  correct_bones              → 归正骨骼原点
Step 1    rename_to_mmd              → XPS 骨名 → MMD 骨名
Step 1.4  transfer_unused_weights    → ★ pelvis→下半身 VG (此时下半身骨还不存在，但 VG 先建)
                                     → spine middle merge
                                     → helper 骨跳过 (twist/preserve)
Step 1.5  fix_forearm_bend           → 前臂弯曲修正
Step 1.6  align_arms_to_canonical    → 手臂方向对齐
Step 1.7  align_fingers_to_canonical → 手指方向对齐
Step 2    complete_missing_bones     → 补全 下半身/腰/グルーブ/上半身3/腰キャンセル
                                     → reparent pelvis→下半身
                                     → reparent 足→腰キャンセル
                                     → 上半身3 权重分割
                                     → 腰キャンセル 付与親=腰(-1.0)
Step 2.5  transfer_unused_weights    → 二次清理 (全ての親/センター/グルーブ 控制骨权重转移)
                                     → pelvis 此时已无 VG，自动跳过
                                     → 上半身→下半身 Z 坐标校正
Step 3    add_mmd_ik                 → IK 骨
Step 4    create_bone_group          → 骨集
Step 5    mmd_convert                → mmd_tools 转换
Step 6    add_leg_d_bones            → D 骨 (copy 主骨权重，不 cut)
Step 7    add_twist_bone             → 捩骨
Step 8    add_shoulder_p_bones       → 肩P
```

**关键时序约束**:
- Step 1.4 必须在 Step 2 之前: pelvis VG 先建，Step 2 创建下半身骨时自动关联
- Step 2 必须在 Step 2.5 之前: 下半身骨先存在，Z 坐标校正才能工作
- Step 6 必须在 Step 5 之后: mmd_convert 改变骨架结构，D 骨需要最终结构

---

## 踩过的坑（按时间顺序）

### 坑 1: unused 骨权重导致颈部拉伸

**现象**: 动画播放时颈部/肩部 mesh 被拽到手臂方向。

**原因**: XPS extra 骨（xtra07 等）被 rename 为 `unused_` 前缀但保留了顶点权重。这些骨的 parent 在手臂链上，动画时把头部顶点拽走了。

**修复**: 创建 `transfer_unused_weights` 操作器，把 unused 骨权重按 per-vertex-nearest 转移到最近的有效变形骨。

**教训**: unused 骨 ≠ 没有权重。rename 后必须处理残留权重。

---

### 坑 2: foretwist 权重被通用 transfer 吃掉

**现象**: 前臂弯曲时 mesh 断裂。

**原因**: `transfer_unused_weights` 把 foretwist/foretwist1 的权重也转移到了 elbow，但这些权重应该留给后面的 twist 操作器处理。

**修复**: 在 transfer 的 SKIP_PATTERNS 里加入 foretwist。后来升级为 auto-classifier 自动识别 twist 类骨。

**教训**: 通用操作器必须有白名单/黑名单机制，不能无差别处理所有 unused 骨。

---

### 坑 3: 上半身/下半身 head 重合，per-vertex-nearest 无法区分

**现象**: 臀部区域 0 权重在下半身上，弯腰时臀部不跟。

**原因**: 上半身和下半身的 `head` 位置完全重合（都在腰椎位置），per-vertex-nearest 总是选到上半身（可能由于骨骼列表顺序）。

**修复**: 加 Z 坐标判断——低于 `上半身.head.z` 的上半身顶点移到下半身。

```python
if vp.z < ub_z - 0.01:
    lb_vg.add([v.index], g.weight, 'ADD')
    ub_vg.remove([v.index])
```

**教训**: per-vertex-nearest 在 head 重合的骨对上完全失效，必须用额外几何判据。

---

### 坑 4: helper 骨合并到主骨，丢失矫正变形

**现象**: 大腿内侧弯曲变形不自然，不如 XPS 原始效果。

**原因**: xtra04/xtra02（大腿内侧 helper）被 merge 到足.L/足.R。这些 helper 骨有独特的轴方向（xtra02 和足.R 夹角 180°），作为矫正骨工作。合并后矫正效果消失。

**修复**: PRESERVE 策略——helper 骨保留 XPS 原始权重和位置，靠 parent-chain 继承旋转。

**教训**: helper 骨不是"多余的骨"。它们存在是有原因的——矫正关节变形。不切权重原则的核心逻辑。

---

### 坑 5: pelvis helper 骨 reparent 到腰，parent 链断裂

**现象**: 下半身旋转时臀部 mesh 撕裂（xtra08/xtra08opp 不跟随）。

**原因**: XPS 的 pelvis 骨 parent=センター（根），xtra08 parent=pelvis。下半身是后创建的骨，pelvis 在センター下面不跟下半身旋转。之前错误地 reparent pelvis→腰，导致 parent 链不匹配。

**修复**: `complete_bones` 后把 `unused bip001 pelvis` reparent 到 `下半身`（不是腰）。

```python
pelvis_bone.parent = lower_body  # 下半身，不是腰
```

**教训**: reparent 要看整条 parent chain 的语义，不能只看直接 parent。pelvis 的 children（xtra08 等）需要跟下半身旋转。

---

### 坑 6: 腰キャンセル additional_transform 指向错误导致腿 IK 抖动

**现象**: reimport PMX 后腿 IK 剧烈抖动，旋转幅度从 15° 暴涨到 166°。

**原因**: 腰キャンセル.L 的 additional_transform_bone 设成了 `下半身`（parent），而非 `腰`（grandparent）。mmd_tools reimport 时创建 `_dummy_腰キャンセル.L` parent=下半身，下半身大旋转叠加到 dummy → TRANSFORM 约束堆叠 → IK solver 发散。

**修复**: additional_transform_bone 必须是 `腰`（比 parent 高一级）。

**教训**: additional_transform 的 target 不能是直接 parent，否则 mmd_tools 的 dummy 骨机制会产生循环依赖。这个坑 Convert_to_MMD 也踩过。

---

### 坑 7: 腰キャンセル 被误识别为大腿骨

**现象**: 腰キャンセル 位置和足.head 重合，skeleton_identifier 把它当成 thigh_bone，导致 xtra04/xtra02 分类错误。

**原因**: `_trace_limb_chain` 返回 `[腰キャンセル, 足, ひざ, 足首]`，chain[0] 的 head 和 chain[1] 的 head 重合——这是控制骨的特征，不是真正的 limb start。

**修复**: `_trace_limb_chain` 跳过 head 重合的 chain[0]（距离 < 0.01）。

**教训**: 控制骨（non-deform）会污染几何分析。skeleton_identifier 需要区分控制骨和变形骨。最终方案：`use_deform=False` 自然排除。

---

### 坑 8: 腰キャンセル use_deform=True 导致收到杂散权重

**现象**: per-vertex-nearest transfer 把大腿区域的 unused 权重分配到腰キャンセル 上。

**原因**: 腰キャンセル 设成了 use_deform=True，被 valid_deform_bones 列表包含，而它的 head 位置正好在大腿根部附近。

**修复**: 对齐 Convert_to_MMD 参考实现，`use_deform=False`。控制骨自然被 valid_deform_bones 排除。

**教训**: 控制骨一定要设 `use_deform=False`。不要用 `is_tip` 之类的 workaround 绕过——根治比止痛好。

---

### 坑 9: pelvis VG 时序 bug（6892 verts 散失）★ 最新

**现象**: 下半身只有 482 verts（target 14168，差 29 倍），足D 反而多了 2000+ 不该有的 verts。

**原因**: 两次 transfer 之间的时序竞争：

```
Step 1.4 (第一次 transfer):
  → pelvis 被 classifier 正确标为 'pelvis'
  → pelvis→下半身 映射块检查 obj.data.bones.get('下半身') → None（骨还没创建）
  → 整块跳过！6892 verts 留在 pelvis VG 上

Step 2 (complete_bones):
  → 创建下半身骨
  → reparent pelvis 到下半身下面（parent 链变了）

Step 2.5 (第二次 transfer):
  → classifier 重跑，pelvis parent=下半身（不再是センター）
  → pelvis 不再被分类为 'pelvis'，变成 'other'
  → 走 per-vertex-nearest → 6892 verts 散到足D/ひざD/上半身等各处
```

**修复**: 去掉 `if lower_body_bone:` 守卫。在第一次 transfer 时就创建下半身 VG 并转移 pelvis 权重，即使下半身骨还不存在。Step 2 创建骨头后会自动关联已有 VG。

```python
# 修复前
lower_body_bone = obj.data.bones.get('下半身')
if lower_body_bone:  # ← 第一次 transfer 时 None，跳过
    ...

# 修复后
if pelvis_bone_names:  # ← 只看有没有 pelvis 骨要转移
    ...
```

**教训**: VG 和 Bone 是独立概念。VG 可以在 Bone 创建之前就存在。多 pass pipeline 中，weight transfer 的守卫条件不能假设后续步骤已经执行。

---

## 下半身权重清理规则

### 严格优势法（唯一正确方法）

```python
# 只在 D 骨权重严格大于下半身权重时才删下半身
if max_d_w > lower_w:
    verts_to_remove.append(v.index)
```

**绝对不能用**:
- `max_d_w >= 0.1` — Reika 上毁了 3510 verts
- `max_d_w > 0` — 同上
- 任何绝对阈值

---

## 不切权重原则详解

| 允许的操作 | 禁止的操作 |
|-----------|-----------|
| copy 权重（足→足D） | merge helper 到主骨 |
| rename VG（pelvis→下半身） | 手动改单顶点权重 |
| 梯度插值（twist gradient split） | 用绝对阈值删权重 |
| PRESERVE helper 骨（保留 XPS 原始权重） | 把"比例低"当 bug 修 |
| per-vertex-nearest（仅用于 unused 'other' 类） | proximity transfer 处理 twist 骨 |

**为什么**: XPS helper 骨（xtra/ThighTwist/muscle_elbow）有独特的轴方向和权重分布，作为矫正骨工作。合并/切割会丢失矫正效果，而且无法可靠恢复——你不知道原作者的意图。

---

## XPS 骨骼分类与处理

### helper_classifier 分类结果 → 处理方式

| 分类 | 含义 | 处理 | 举例 |
|------|------|------|------|
| mapped | skeleton_identifier 已匹配 | rename 到 MMD 名 | root hips→センター |
| twist | 手臂段 twist 候选 | twist operator 处理 | foretwist, xtra07 |
| pelvis | center 直接子骨，居中 | 直接映射到下半身 VG | bip001 pelvis |
| preserve | 大腿/臀部/胸部 helper | 保留原始权重 | xtra04, xtra02, xtra08 |
| merge | 中间 spine 段 | per-vertex-nearest 合入 | spine middle |
| control | 非变形控制骨 | 清空权重 | 全ての親, センター |
| other | 未分类 unused | per-vertex-nearest | hair, face bones |

### 分类判据（按优先级）

1. 已被 skeleton_identifier 匹配 → `mapped`
2. head 后代 → `other`（hair/face 骨，不是 twist）
3. hand 后代 → `other`（carpal 骨）
4. center 直接子骨 + 居中(|x|<0.02) → `pelvis`
5. center 子骨 + 偏侧 → `preserve`
6. 在手臂段附近 → `twist`
7. 在大腿段附近 → `preserve`
8. thigh 后代 → `preserve`
9. spine 后代 + 偏侧 → `preserve`（胸部 helper）
10. spine 后代 + 居中 → `merge`（中间 spine 段）
11. 其余 → `other`

---

## 诊断顺序: L4 → L1 → L2 → L3

遇到"腿/腰/臀看着不对"时，**严格按此顺序排查，不跳步**:

### L4 语义层
- rename log 有无 Missing？
- VMD 能否按名字找到骨骼？
- helper 分类是否正确？（pelvis/twist/preserve）

### L1 几何层
- rest pose 对齐了吗？（arm alignment, finger alignment）
- complete_bones 补全了吗？（下半身/腰/上半身3/腰キャンセル）
- 骨方向（matrix_local）是否匹配 target？

### L2 约束/Parent 链层
- 腰キャンセル additional_transform = 腰（不是下半身）？
- twist 骨 additional_transform 设了吗？
- helper 骨 parent 链正确吗？（xtra08→pelvis→下半身）
- **诊断技巧**: Pose Mode 旋转 parent 骨，看 child 是否跟随

### L3 蒙皮层（最后手段）
- 只在 L4/L1/L2 全排除后才动
- 只用保守操作（copy/rename/gradient split）
- **永远不手动改单顶点权重**

---

## 两种模型架构

### Inase (XNA Lara 系)
- helper 骨: xtra02/04 (parent=thigh) + xtra08/08opp (parent=pelvis)
- 全部 PRESERVE，靠 parent-chain 继承
- 足D 权重比例低（2.7% vs target 15.1%）是 mesh 密度差异，不是 bug

### Reika (DAZ Genesis 8 系)
- 有 lThighTwist/rThighTwist (parent=足.L)，没有 parent=pelvis helper
- ThighTwist 自动保留（无 `unused` 前缀）
- 下半身清理必须用严格优势法（没有 helper 骨补偿，删错直接爆）

**同一 pipeline 同时通过两种架构 = 设计正确。**

---

## 快速排查清单

遇到臀部/大腿问题时按顺序检查:

1. [ ] 骨骼名正确？rename log 有无 Missing？
2. [ ] helper 分类正确？pelvis→`pelvis`，xtra04/02→`preserve`？
3. [ ] pelvis 权重到下半身了？（看第一次 transfer 的 `pelvis → 下半身 (direct): N verts` 日志）
4. [ ] rest pose 对齐？arm/finger alignment 角度合理？
5. [ ] 腰キャンセル 存在？parent=下半身？additional_transform=腰(-1.0)？use_deform=False？
6. [ ] Pose Mode 旋转足.L → xtra04/足D.L 跟随？
7. [ ] helper 骨 parent 链完整？（xtra08→pelvis→下半身，不是→センター）
8. [ ] 上半身→下半身 Z 校正执行了？
9. [ ] 全ての親/センター VG 清理了？
10. [ ] 如果确认是 L3: 是 Lower Body Cleanup 过度删除？用的严格优势法？**永远不手动改单顶点。**

---

## 关键文件索引

| 文件 | 内容 |
|------|------|
| `operators/xps_fixes_operator.py` | pelvis→下半身 映射, unused 转移, Z 校正 |
| `operators/complete_bones_operator.py` | 下半身/腰キャンセル 创建, pelvis reparent |
| `operators/add_leg_d_bones_operator.py` | D 骨创建, reparent 到腰キャンセル |
| `helper_classifier.py` | 位置+parent 自动分类 |
| `skeleton_identifier.py` | 骨架识别, limb chain 追踪 |
| `doc/waist_cancel_plan.md` | 腰キャンセル 设计文档 |

---

## Convert_to_MMD 参考实现对照

| 功能 | Convert_to_MMD | xps_to_mmd |
|------|---------------|------------|
| pelvis 处理 | `FORCED_TARGETS = {"pelvis": "下半身"}` 全量映射 | pelvis→下半身 VG (direct) |
| 腰キャンセル | `bone_operator.py:394` use_deform=False | `complete_bones_operator.py` 同 |
| 腰キャンセル清空 | `leg_operator.py:1206` 显式清空权重 | use_deform=False 自动排除 |
| D 骨 parent | `leg_operator.py:174` parent=腰キャンセル | `add_leg_d_bones_operator.py` 同 |
| 付与親 | `preset_operator.py:153` target=腰(-1.0) | `complete_bones_operator.py` 同 |
| 下半身清理 | `leg_operator.py:715` 严格优势 | 暂未独立实现(靠 Z 校正覆盖) |
