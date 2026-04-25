# MMD 骨骼规格总表

> 每种骨骼类型的 use_deform、parent、constraint、付与親、权重要求。
> 重新实现时按此表逐项检查，不会犯错。
> 最后更新: 2026-04-25

---

## 骨骼层级总览

```
全ての親 (root)
  └─ センター (center)
       └─ グルーブ (groove)
            └─ 腰 (waist)
                 ├─ 上半身 → 上半身2 → 上半身3 → 首 → 頭
                 │    ├─ 左肩P → 左肩 → 左腕 → 左ひじ → 左手首 → fingers
                 │    └─ 右肩P → 右肩 → 右腕 → 右ひじ → 右手首 → fingers
                 └─ 下半身
                      ├─ 腰キャンセル.L → 左足 → 左ひざ → 左足首 → 左足先EX
                      └─ 腰キャンセル.R → 右足 → 右ひざ → 右足首 → 右足先EX
  ├─ 左足IK親 → 左足ＩＫ → 左つま先ＩＫ
  └─ 右足IK親 → 右足ＩＫ → 右つま先ＩＫ
```

D 骨、捩骨、_dummy_、_shadow_ 在下方各节详述。

---

## 1. 控制骨（非変形）

VMD 驱动旋转/位移，但**不直接影响 mesh 変形**。

| 骨骼 | parent | use_deform | 権重 | constraint | 付与親 | 说明 |
|------|--------|-----------|------|-----------|-------|------|
| 全ての親 | None | **False** | 0 | 无 | 无 | 根骨，VMD 全体移動 |
| センター | 全ての親 | **False** | 0 | 无 | 无 | VMD 重心移動 |
| グルーブ | センター | **False** | 0 | 无 | 无 | VMD グルーブモーション |
| 腰 | グルーブ | **False** | 0 | 无 | 无 | 上下半身分岐点 |
| 操作中心 | センター | **False** | 0 | 无 | 无 | 可选，编辑辅助 |

**要点**：
- `use_deform=False` → 不出现在 valid_deform_bones 列表 → per-vertex-nearest 不会把权重分配到这些骨上
- 如果有残留权重必须在 transfer_unused_weights 中清零
- Target PMX (mmd_tools 导入) 会把这些设为 `use_deform=True`，但实际权重为 0，功能无区别

---

## 2. 主変形骨

VMD 直接驱动，有 mesh 権重。

| 骨骼 | parent | use_deform | constraint | 付与親 | 说明 |
|------|--------|-----------|-----------|-------|------|
| 上半身 | 腰 | True | 无 | 无 | 胴体上部 |
| 上半身1 | 上半身 | True | 无 | 无 | 腹部（auto 从上半身 split） |
| 上半身2 | 上半身1 | True | 无 | 无 | 胸部 |
| 上半身3 | 上半身2 | True | 无 | 无 | 锁骨区域（auto 从上半身2 split） |
| 下半身 | 腰 | True | 无 | 无 | 臀部/腰部 |
| 首 | 上半身3 | True | 无 | 无 | 颈 |
| 頭 | 首 | True | 无 | 无 | 头 |
| 左肩/右肩 | 上半身3 | True | 无 | 无 | 肩 |
| 左腕/右腕 | 左肩/右肩 | True | 无 | 无 | 上腕 |
| 左ひじ/右ひじ | 左腕/右腕 | True | 无 | 无 | 肘 |
| 左手首/右手首 | 左ひじ/右ひじ | True | 无 | 无 | 手首 |
| 左足/右足 | 腰キャンセル.L/.R | True | 无 | 无 | 大腿 |
| 左ひざ/右ひざ | 左足/右足 | True | 无 | 无 | 膝 |
| 左足首/右足首 | 左ひざ/右ひざ | True | 无 | 无 | 足首 |
| 左足先EX/右足先EX | 左足首/右足首 | True | 无 | 无 | 足先 |
| 左目/右目 | 頭 | True | 无 | 无 | 眼睛 |
| 左人指０/右人指０ | 手首 | True | 无 | 无 | 人差指根 (pass-through) |
| 左中指０/右中指０ | 手首 | True | 无 | 无 | 中指根 (pass-through) |
| 左薬指０/右薬指０ | 手首 | True | 无 | 无 | 薬指根 (pass-through) |
| 左小指０/右小指０ | 手首 | True | 无 | 无 | 小指根 (pass-through) |
| 親指０~２ ×2 | 手首/親指 | True | 无 | 无 | 親指 |
| 指１~３ ×8 | 指根０ | True | 无 | 无 | 指骨 |

**要点**：
- D 骨创建后，足/ひざ/足首 の VG 権重应被 copy 到 D 骨，**原骨権重清零**
- 上半身1 的权重由 `_split_chain_weights` 从上半身 split 得来（上半身 と 上半身2 の中点）
- 上半身3 的权重由 `_split_chain_weights` 从上半身2 split 得来
- 下半身 的权重包含 pelvis VG 直接映射（在 complete_bones 之前就建好 VG）
- 首1 的权重由 `_split_chain_weights` 从首 split 得来
- D 骨创建后，足/ひざ/足首 の VG 権重 copy 到 D 骨，**原骨清零**
- 指根骨 (人指０ 等) 是 pass-through，位置 = midpoint(手首.head, 指１.head)，0 権重
- 指１ の parent 从手首改为対応指根骨

---

## 3. D 骨（準標準骨）

**完全复制**对应主骨的旋转。VMD 不直接驱动 D 骨，通过 TRANSFORM constraint 从主骨同步。

| 骨骼 | parent | use_deform | 付与親 target | 付与親 influence |
|------|--------|-----------|-------------|---------------|
| 左足D/右足D | 腰キャンセル.L/.R | True | 左足/右足 | 1.0 |
| 左ひざD/右ひざD | 左足D/右足D | True | 左ひざ/右ひざ | 1.0 |
| 左足首D/右足首D | 左ひざD/右ひざD | True | 左足首/右足首 | 1.0 |

### TRANSFORM constraint（D 骨 → _shadow_）

```
type:         TRANSFORM
target:       自身 Armature
subtarget:    _shadow_<D骨名>
influence:    1.0
owner_space:  LOCAL
target_space: LOCAL
map_from:     ROTATION
map_to:       ROTATION
mix_mode_rot: ADD          ← 必须是 ADD，不是 AFTER
from_rotation_mode: XYZ
to_euler_order:     XYZ
from_rot:     X/Y/Z = [-π, +π]
to_rot:       X/Y/Z = [-π, +π]   (1:1 完全复制)
```

**mix_mode_rot 为什么必须是 ADD**：
- D 骨自身旋转通常为 0（VMD 不驱动）
- ADD: `0 + 主骨旋转 = 主骨旋转`（纯加法，坐标系不变）
- AFTER: 先算自身旋转(0°)再在结果空间叠加 → 自身旋转为 0 时和 ADD 一样，但有任何微小偏差时结果轴向会偏
- MMD 标准就是 ADD

### D 骨権重

- D 骨 VG = 主骨 VG 的完整拷贝（copy，不是 move）
- 创建 D 骨后，主骨（足/ひざ/足首）的 VG **应清零**
- D 骨是实际控制 mesh 变形的骨，主骨只驱动旋转

---

## 4. 腰キャンセル骨

抵消腰旋转，让腿 IK 不受腰转影响。

| 骨骼 | parent | use_deform | 付与親 target | influence |
|------|--------|-----------|-------------|-----------|
| 腰キャンセル.L | 下半身 | **False** | 腰 | **-1.0** |
| 腰キャンセル.R | 下半身 | **False** | 腰 | **-1.0** |

### 约束

Target reimport 后 mmd_tools 会展开为 TRANSFORM constraint：

```
type:         TRANSFORM
subtarget:    _shadow_腰キャンセル.L
mix_mode_rot: ADD
influence:    1.0
from/to_rot:  [-π, +π] → [+π, -π]   (注意反向！反转旋转)
```

Auto 不需要显式 TRANSFORM（用 mmd_bone 属性代替，`apply_additional_transform` 后等价）。

**要点**：
- `use_deform=False` → 没有权重，不变形 mesh
- 付与親 target 必须是 **腰**（grandparent），不是下半身（parent）
  - 如果指向下半身 → mmd_tools reimport 时 _dummy_ 骨 parent=下半身 → 下半身大旋转叠加 → 腿 IK 抖动
- head 位置 = 对应足.head（和足骨完全重合）
- 足/足D 的 parent 是腰キャンセル（不是下半身）

---

## 5. 肩P 骨

让肩跟随上半身3旋转但有独立控制。

| 骨骼 | parent | use_deform | constraint | 付与親 |
|------|--------|-----------|-----------|-------|
| 左肩P/右肩P | 上半身3 | True | 无 | 无 |

**要点**：
- 肩P 是肩的 parent（肩P → 肩 → 腕）
- use_deform=True 但通常权重为 0（肩承担変形）
- 无 constraint、无付与親

---

## 6. 捩骨（手腕扭转）

在上腕→肘→手首的区间内做 twist 插值。

### 主捩骨（rename 自 XPS twist 候选骨）

| 骨骼 | parent | use_deform | 付与親 | 说明 |
|------|--------|-----------|-------|------|
| 左腕捩/右腕捩 | 左腕/右腕 | True | 无 | 上腕 twist 主骨 |
| 左手捩/右手捩 | 左ひじ/右ひじ | True | 无 | 前腕 twist 主骨 |

### 捩サブ骨（gradient split 分配点）

| 骨骼 | parent | use_deform | 付与親 target | influence |
|------|--------|-----------|-------------|-----------|
| 左腕捩1 | 左腕捩 | True | 左腕捩 | 0.25 |
| 左腕捩2 | 左腕捩 | True | 左腕捩 | 0.50 |
| 左腕捩3 | 左腕捩 | True | 左腕捩 | 0.75 |
| 左手捩1 | 左手捩 | True | 左手捩 | 0.25 |
| 左手捩2 | 左手捩 | True | 左手捩 | 0.50 |
| 左手捩3 | 左手捩 | True | 左手捩 | 0.75 |

### TRANSFORM constraint（捩サブ骨）

```
type:         TRANSFORM
subtarget:    _shadow_<捩サブ骨名>
mix_mode_rot: ADD
influence:    1.0
from_rot:     X/Y/Z = [-π, +π]
to_rot:       X/Y/Z = [-angle, +angle]   (angle = 45° × index)
  捩1: ±45°, 捩2: ±90°, 捩3: ±135°
```

**要点**：
- 捩サブ骨 的 to_rot 不是 1:1，而是按 influence 缩放（0.25/0.50/0.75 对应 45°/90°/135°）
- 捩主骨没有 TRANSFORM constraint，靠 parent chain 继承旋转
- gradient split 将腕/ひじ 的权重按位置分配到捩サブ骨上
- 源骨（腕/ひじ）保留按距离递减的权重（`retain = orig_w × (1-t)`）

---

## 付与親 (additional_transform) 系統

MMD 的付与親是骨骼间旋转/位移联动的核心机制。一个骨骼设了付与親后，它的变换会自动跟随目标骨骼。

### PMX 层（mmd_bone 属性）

在 Blender 里通过 `pose_bone.mmd_bone` 设定：

```python
pb.mmd_bone.has_additional_rotation = True    # 启用旋转联动
pb.mmd_bone.has_additional_location = False   # 通常不需要位移联动
pb.mmd_bone.additional_transform_bone = "目标骨名"  # 跟随谁
# additional_transform_bone_id 是内部索引，自动管理
```

### Blender 実装（_dummy_ / _shadow_ / TRANSFORM 三件套）

PMX 的付与親在 Blender 里无法直接实现，mmd_tools 通过三个辅助结构模拟：

```
目標骨 (e.g. 左足) 旋转
  │
  ├─ _dummy_左足D    ← parent=左足, 无 constraint
  │   通过 parent chain 自动继承左足的旋转
  │
  ├─ _shadow_左足D   ← parent=腰キャンセル.L (=左足D 的 parent)
  │   COPY_TRANSFORMS ← _dummy_左足D
  │   把 _dummy_ 的世界空間 transform 复制过来
  │
  └─ 左足D           ← parent=腰キャンセル.L
      TRANSFORM ← _shadow_左足D (mix=ADD)
      从 _shadow_ 读取旋转，ADD 到自身
      → mesh 変形
```

**为什么需要三件套而不直接读目標骨**：Blender 的 constraint 求值顺序问题。如果 D 骨直接读目標骨，
在某些更新顺序下会延迟一帧。通过 _dummy_(parent chain) → _shadow_(COPY) → TRANSFORM 的中介链
可以保证同帧同步。

### 哪些骨用了付与親

| 骨骼 | 付与親 target | influence | 说明 |
|------|-------------|-----------|------|
| 左足D/右足D | 左足/右足 | 1.0 (rot) | D 骨完全复制主骨旋转 |
| 左ひざD/右ひざD | 左ひざ/右ひざ | 1.0 (rot) | 同上 |
| 左足首D/右足首D | 左足首/右足首 | 1.0 (rot) | 同上 |
| 腰キャンセル.L/.R | 腰 | **-1.0** (rot) | 反向抵消腰旋转 |
| 左腕捩1~3 | 左腕捩 | 0.25/0.50/0.75 (rot) | 分段跟随 twist |
| 左手捩1~3 | 左手捩 | 0.25/0.50/0.75 (rot) | 同上 |

### apply_additional_transform

`bpy.ops.mmd_tools.apply_additional_transform()` 把 mmd_bone 属性展开为实际的 _dummy_/_shadow_/TRANSFORM constraint。
Pipeline 里必须在所有骨骼创建完成后调用一次（one_click 的 step 8.5）。

**不调用的后果**：mmd_bone 属性只是元数据，不会真正影响骨骼行为。D 骨不跟主骨旋转，腰キャンセル 不抵消腰旋转。

---

## 7. _dummy_ 骨

付与親系统的 parent chain 中继。`_dummy_` 骨通过 parent=目標骨 来继承旋转。

| 骨骼 | parent | use_deform | constraint |
|------|--------|-----------|-----------|
| _dummy_左足D | 左足 | False | 无 |
| _dummy_左ひざD | 左ひざ | False | 无 |
| _dummy_左足首D | 左足首 | False | 无 |
| _dummy_腰キャンセル.L | 腰 | False | 无 |
| _dummy_左腕捩1 | 左腕捩 | False | 无 |
| _dummy_左手捩1 | 左手捩 | False | 无 |
| _dummy_左肩C | 左肩P | False | 无 |

**parent 规则**：`_dummy_<X>` 的 parent = X 的付与親 target 骨。

例如 `_dummy_左足D` parent=`左足`，因为 `左足D` 的付与親 target=`左足`。

**没有 constraint**——_dummy_ 纯粹通过 parent chain 继承 target 骨的旋转。

---

## 8. _shadow_ 骨

_shadow_ 骨是 _dummy_ 的"世界空间镜像"，通过 COPY_TRANSFORMS 从 _dummy_ 复制 transform，供 TRANSFORM constraint 读取。

| 骨骼 | parent | use_deform | constraint |
|------|--------|-----------|-----------|
| _shadow_左足D | 腰キャンセル.L | False | COPY_TRANSFORMS → _dummy_左足D |
| _shadow_左ひざD | 左足 | False | COPY_TRANSFORMS → _dummy_左ひざD |
| _shadow_左足首D | 左ひざ | False | COPY_TRANSFORMS → _dummy_左足首D |
| _shadow_腰キャンセル.L | 腰 | False | COPY_TRANSFORMS → _dummy_腰キャンセル.L |

### COPY_TRANSFORMS constraint

```
type:         COPY_TRANSFORMS
target:       自身 Armature
subtarget:    _dummy_<対応骨名>
influence:    1.0
owner_space:  POSE
target_space: POSE
```

**parent 规则**：`_shadow_<X>` 的 parent = X 的 parent 骨。

例如 `_shadow_左足D` parent=`腰キャンセル.L`，因为 `左足D` 的 parent=`腰キャンセル.L`。

### 信号链

```
主骨旋转 (e.g. 左足)
   → _dummy_左足D (parent=左足, 继承旋转)
      → COPY_TRANSFORMS → _shadow_左足D (复制 _dummy_ 的 transform)
         → TRANSFORM constraint → 左足D (读取 _shadow_ 的旋转, mix=ADD)
            → mesh 変形
```

**为什么不直接用主骨做 TRANSFORM source**：
Blender 的 constraint 求值顺序问题。如果 D 骨直接读主骨，在某些更新顺序下会延迟一帧。通过 _dummy_/_shadow_ 中介可以保证同帧同步。

---

## 9. IK 骨

| 骨骼 | parent | use_deform | constraint | 说明 |
|------|--------|-----------|-----------|------|
| 左足IK親 | 全ての親 | False | 无 | IK chain 根 |
| 左足ＩＫ | 左足IK親 | False | IK (target=左足首) | 足 IK |
| 左つま先ＩＫ | 左足ＩＫ | False | IK (target=左足先EX) | 足先 IK |

**要点**：
- IK 骨 parent 在全ての親下面（独立于身体骨骼链），这样移動 IK handle 时不受身体旋转影响
- use_deform=False，无権重

---

## 10. XPS Helper 骨（PRESERVE）

XPS 模型特有的辅助骨，保留原始权重不做任何处理。

| 骨骼 (Inase) | parent | use_deform | 处理方式 |
|-------------|--------|-----------|---------|
| unused bip001 xtra04 | 左足 | True | PRESERVE（大腿内侧 helper） |
| unused bip001 xtra02 | 右足 | True | PRESERVE（大腿内侧 helper） |
| unused bip001 xtra08 | unused bip001 pelvis | True | PRESERVE（臀部 helper） |
| unused bip001 xtra08opp | unused bip001 pelvis | True | PRESERVE（臀部 helper） |
| unused bip001 pelvis | 下半身 | True | 権重 → 下半身 VG（直接映射，非 per-vertex-nearest） |
| boob left/right 1/2 | 上半身2 | True | PRESERVE（胸部 helper） |

**要点**：
- 不切权重原则：这些骨有独特轴向和 XPS 原始权重分布，合并会丢失矫正变形
- pelvis 的 parent 必须是下半身（不是センター），否则 xtra08 不跟下半身旋转 → 臀部撕裂

---

## 快速检查表

新建或排查骨骼时，按此表逐项验证：

```
□ use_deform 正确？（控制骨=False, 変形骨=True）
□ parent chain 正确？（参照层级图）
□ 付与親 target 正确？（D骨→主骨, 腰キャンセル→腰）
□ TRANSFORM constraint:
    □ mix_mode_rot = ADD？（不是 AFTER）
    □ subtarget = _shadow_<骨名>？
    □ from/to rot 范围正确？（D骨=1:1, 捩サブ=缩放）
□ _dummy_ parent = 付与親 target 骨？
□ _shadow_ parent = 本骨 parent？
□ _shadow_ 有 COPY_TRANSFORMS → _dummy_？
□ VG 権重正确？（D骨创建后主骨清零, 控制骨=0）
```
