# MMD 骨骼规格总表

> 每种骨骼类型的 use_deform、parent、constraint、付与親、权重要求。
> 重新实现时按此表逐项检查，不会犯错。
> 最后更新: 2026-04-25

---

## 骨骼层级总览

```
全ての親 (root)
  ├─ センター (center)
  │    └─ グルーブ (groove)
  │         └─ 腰 (waist)
  │              ├─ 上半身 → 上半身1 → 上半身2 → 上半身3
  │              │    ├─ 首 → 首1 → 頭
  │              │    ├─ 左肩P → 左肩 → [左肩C] → 左腕 → 左腕捩 → 左ひじ → 左手捩 → 左手首
  │              │    │                                                          ├─ 左人指０ → 左人指１~３
  │              │    │                                                          ├─ 左中指０ → 左中指１~３
  │              │    │                                                          ├─ 左薬指０ → 左薬指１~３
  │              │    │                                                          ├─ 左小指０ → 左小指１~３
  │              │    │                                                          └─ 左親指０~２
  │              │    └─ (右側同構造)
  │              └─ 下半身
  │                   ├─ 腰キャンセル.L → 左足 → 左ひざ → 左足首 → 左足先EX
  │                   │                  左足D → 左ひざD → 左足首D  (D骨、parent=腰キャンセル)
  │                   └─ 腰キャンセル.R → (右側同構造)
  ├─ 左足IK親 → 左足ＩＫ → 左つま先ＩＫ
  └─ 右足IK親 → 右足ＩＫ → 右つま先ＩＫ

[肩C] = apply_additional_transform 自動生成
D骨、捩骨、_dummy_、_shadow_ 在下方各節詳述
```

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
- Target PMX (mmd_tools 导入) 会把这些设为 `use_deform=True`，但実際権重为 0，功能無区別

---

## 2. 主変形骨

VMD 直接驱动，有 mesh 権重。

| 骨骼 | parent | use_deform | constraint | 付与親 | 说明 |
|------|--------|-----------|-----------|-------|------|
| 上半身 | 腰 | True | 无 | 无 | 胴体上部 |
| 上半身1 | 上半身 | True | 无 | 无 | 腹部（auto 从上半身 split） |
| 上半身2 | 上半身1 | True | 无 | 无 | 胸部 |
| 上半身3 | 上半身2 | True | 无 | 无 | 鎖骨（auto 从上半身2 split） |
| 下半身 | 腰 | True | 无 | 无 | 臀部/腰部 |
| 首 | 上半身3 | True | 无 | 无 | 頸 |
| 首1 | 首 | True | 无 | 无 | 頸上部（auto 从首 split） |
| 頭 | 首1 | True | 无 | 无 | 頭 |
| 左肩/右肩 | 左肩P/右肩P | True | 无 | 无 | 肩 |
| 左腕/右腕 | 左肩C/右肩C | True | 无 | 无 | 上腕（肩C 是 apply_additional_transform 自動生成） |
| 左ひじ/右ひじ | 左腕/右腕 | True | 无 | 无 | 肘 |
| 左手首/右手首 | 左ひじ/右ひじ | True | 无 | 无 | 手首 |
| 左足/右足 | 腰キャンセル.L/.R | True | 无 | 无 | 大腿 |
| 左ひざ/右ひざ | 左足/右足 | True | 无 | 无 | 膝 |
| 左足首/右足首 | 左ひざ/右ひざ | True | 无 | 无 | 足首 |
| 左足先EX/右足先EX | 左足首/右足首 | True | 无 | 无 | 足先 |
| 左目/右目 | 頭 | True | 无 | 无 | 眼睛 |

### 指骨

| 骨骼 | parent | use_deform | 権重 | 说明 |
|------|--------|-----------|------|------|
| 左親指０~２ | 手首→親指０→親指１ | True | XPS 原始 | 親指（XPS 有 3 段） |
| 左人指０ | 手首 | True | **0** | 指根 pass-through |
| 左人指１~３ | 人指０→１→２ | True | XPS 原始 | 人差指 |
| 左中指０ | 手首 | True | **0** | 指根 pass-through |
| 左中指１~３ | 中指０→１→２ | True | XPS 原始 | 中指 |
| 左薬指０ | 手首 | True | **0** | 指根 pass-through |
| 左薬指１~３ | 薬指０→１→２ | True | XPS 原始 | 薬指 |
| 左小指０ | 手首 | True | **0** | 指根 pass-through |
| 左小指１~３ | 小指０→１→２ | True | XPS 原始 | 小指 |

**要点**：
- 上半身1: `_split_chain_weights` 从上半身 split（上半身 と 上半身2 の中点）
- 上半身3: `_split_chain_weights` 从上半身2 split
- 首1: `_split_chain_weights` 从首 split（首 と 頭 の中点）
- 下半身: pelvis VG 直接映射（在 complete_bones 之前就建好 VG）
- D 骨创建後、足/ひざ/足首 の VG 権重 copy 到 D 骨、**原骨清零**
- 指根骨 (人指０ 等) = pass-through、位置 = midpoint(手首.head, 指１.head)、0 権重
- 指１ の parent 从手首改為対応指根骨

---

## 3. D 骨（準標準骨）

**完全複製**対応主骨的旋转。VMD 不直接驱動 D 骨、通过 TRANSFORM constraint 从主骨同期。

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
mix_mode_rot: ADD          ← 必須是 ADD、不是 AFTER
from_rotation_mode: XYZ
to_euler_order:     XYZ
from_rot:     X/Y/Z = [-π, +π]
to_rot:       X/Y/Z = [-π, +π]   (1:1 完全複製)
```

**mix_mode_rot 為什麼必須是 ADD**：
- D 骨自身旋转通常為 0（VMD 不驱動）
- ADD: `0 + 主骨旋转 = 主骨旋转`（純加法、座標系不変）
- AFTER: 先算自身旋转(0°)再在結果空間疊加 → 有任何微小偏差時結果軸向会偏
- MMD 標準就是 ADD

### D 骨権重

- D 骨 VG = 主骨 VG 的完整拷貝（copy、不是 move）
- 創建 D 骨後、主骨（足/ひざ/足首）的 VG **清零**
- D 骨是実際控制 mesh 変形的骨、主骨只驅動旋转

---

## 4. 腰キャンセル骨

抵消腰旋转、讓腿 IK 不受腰転影響。

| 骨骼 | parent | use_deform | 付与親 target | influence |
|------|--------|-----------|-------------|-----------|
| 腰キャンセル.L | 下半身 | **False** | 腰 | **-1.0** |
| 腰キャンセル.R | 下半身 | **False** | 腰 | **-1.0** |

### 約束

`apply_additional_transform` 後展開為 TRANSFORM constraint：

```
type:         TRANSFORM
subtarget:    _shadow_腰キャンセル.L
mix_mode_rot: ADD
influence:    1.0
from/to_rot:  [-π, +π] → [+π, -π]   (注意反向！反転旋転)
```

**要点**：
- `use_deform=False` → 没有権重、不変形 mesh
- 付与親 target 必須是 **腰**（grandparent）、不是下半身（parent）
  - 如果指向下半身 → mmd_tools reimport 時 _dummy_ 骨 parent=下半身 → 下半身大旋転疊加 → 腿 IK 抖動
- head 位置 = 対応足.head（和足骨完全重合）
- 足/足D 的 parent 是腰キャンセル（不是下半身）

---

## 5. 肩P / 肩C 骨

肩P 讓肩有獨立於上半身3 的控制。肩C 讓肩的 child chain 跟隨肩P 旋転。

| 骨骼 | parent | use_deform | 権重 | constraint | 付与親 |
|------|--------|-----------|------|-----------|-------|
| 左肩P/右肩P | 上半身3 | True | 0 | 无 | 无 |
| 左肩C/右肩C | 左肩/右肩 | True | 0 | TRANSFORM→_shadow_肩C (ADD) | rot→肩P |

**parent chain**:
```
上半身3
  └─ 肩P  (VMD 驱動, 獨立控制肩旋転)
       └─ 肩  (主変形骨, 有権重)
            └─ 肩C  (付与親→肩P, 自動生成)
                 └─ 腕 → 腕捩 → ひじ → 手捩 → 手首
```

**要点**：
- 肩P 和 肩C 都是 0 権重（肩承擔変形）
- 肩C 由 `apply_additional_transform` 自動創建、pipeline 中不需要手動創建
- _dummy_肩C parent=肩P, _shadow_肩C parent=上半身3

### ダミー骨

mmd_tools 創建的占位骨（PMX reimport 時出現、pipeline 不需要創建）。

| 骨骼 | parent | use_deform | 権重 | 说明 |
|------|--------|-----------|------|------|
| ダミー.L/.R | 手首 | True | 0 | 手首 placeholder |
| 操作中心 | None | True | 0 | UI 操作辅助 |

---

## 6. 捩骨（手腕扭転）

在上腕→肘→手首的区間内做 twist 插値。

### 主捩骨（rename 自 XPS twist 候補骨）

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

### _dummy_ / _shadow_（捩サブ骨）

| 骨骼 | parent | use_deform | constraint |
|------|--------|-----------|-----------|
| _dummy_左腕捩1~3 | 左腕捩 | **False** | 无 |
| _dummy_左手捩1~3 | 左手捩 | **False** | 无 |
| _shadow_左腕捩1~3 | 左腕 | **False** | COPY_TRANSFORMS → _dummy_ |
| _shadow_左手捩1~3 | 左ひじ | **False** | COPY_TRANSFORMS → _dummy_ |

**要点**：
- 捩サブ骨 的 to_rot 不是 1:1、按 influence 縮放（0.25/0.50/0.75 対応 45°/90°/135°）
- 捩主骨没有 TRANSFORM constraint、靠 parent chain 继承旋転
- gradient split:
  - 腕→ひじ: redistributive（腕 権重拆分到 腕捩サブ骨）
  - ひじ→手首: **additive**（ひじ 権重保留、手捩サブ骨叠加）
- _dummy_/_shadow_ 的 use_deform=**False**

---

## 付与親 (additional_transform) 系統

MMD 的付与親是骨骼間旋転/位移聯動的核心機制。

### PMX 層（mmd_bone 属性）

```python
pb.mmd_bone.has_additional_rotation = True    # 啟用旋転聯動
pb.mmd_bone.has_additional_location = False   # 通常不需要位移聯動
pb.mmd_bone.additional_transform_bone = "目標骨名"  # 跟隨誰
```

### Blender 実装（_dummy_ / _shadow_ / TRANSFORM 三件套）

PMX 的付与親在 Blender 里無法直接実現、mmd_tools 通過三個辅助結構模擬：

```
目標骨 (e.g. 左足) 旋転
  │
  ├─ _dummy_左足D    ← parent=左足, 無 constraint
  │   通過 parent chain 自動繼承左足的旋転
  │
  ├─ _shadow_左足D   ← parent=腰キャンセル.L (=左足D 的 parent)
  │   COPY_TRANSFORMS ← _dummy_左足D
  │   把 _dummy_ 的世界空間 transform 複製過来
  │
  └─ 左足D           ← parent=腰キャンセル.L
      TRANSFORM ← _shadow_左足D (mix=ADD)
      从 _shadow_ 読取旋転、ADD 到自身
      → mesh 変形
```

**為什麼需要三件套**：Blender 的 constraint 求値順序問題。直接讀目標骨可能延遲一幀。
通過 _dummy_(parent chain) → _shadow_(COPY) → TRANSFORM 的中介鏈保証同幀同期。

### 付与親一覧

| 骨骼 | 付与親 target | influence | 说明 |
|------|-------------|-----------|------|
| 足D (×2) | 足 | 1.0 (rot) | D 骨完全複製 |
| ひざD (×2) | ひざ | 1.0 (rot) | 同上 |
| 足首D (×2) | 足首 | 1.0 (rot) | 同上 |
| 腰キャンセル (×2) | 腰 | **-1.0** (rot) | 反向抵消 |
| 肩C (×2) | 肩P | 1.0 (rot) | 肩連動（自動生成） |
| 腕捩1~3 (×6) | 腕捩 | 0.25/0.50/0.75 | 分段 twist |
| 手捩1~3 (×6) | 手捩 | 0.25/0.50/0.75 | 分段 twist |

### apply_additional_transform

`bpy.ops.mmd_tools.apply_additional_transform()` 把 mmd_bone 属性展開為 _dummy_/_shadow_/TRANSFORM。
Pipeline 里必須在所有骨骼創建完成後調用一次（one_click 的 step 8.5）。

**同時自動創建**：肩C 骨、所有 _dummy_/_shadow_ 骨。不需要手動創建。

**不調用的後果**：mmd_bone 属性只是元数据、不会真正影響骨骼行為。

---

## 7. _dummy_ 骨

付与親系統的 parent chain 中繼。通過 parent=目標骨 来繼承旋転、無 constraint。

| 骨骼 | parent | use_deform |
|------|--------|-----------|
| _dummy_足D | 足 | False |
| _dummy_ひざD | ひざ | False |
| _dummy_足首D | 足首 | False |
| _dummy_腰キャンセル | 腰 | False |
| _dummy_肩C | 肩P | False |
| _dummy_腕捩1~3 | 腕捩 | False |
| _dummy_手捩1~3 | 手捩 | False |

**parent 規則**：`_dummy_<X>` 的 parent = X 的付与親 target 骨。

---

## 8. _shadow_ 骨

_dummy_ 的世界空間鏡像。COPY_TRANSFORMS 从 _dummy_ 複製 transform、供 TRANSFORM constraint 読取。

| 骨骼 | parent | use_deform | constraint |
|------|--------|-----------|-----------|
| _shadow_足D | 腰キャンセル | False | COPY_TRANSFORMS → _dummy_足D |
| _shadow_ひざD | 足 | False | COPY_TRANSFORMS → _dummy_ひざD |
| _shadow_足首D | ひざ | False | COPY_TRANSFORMS → _dummy_足首D |
| _shadow_腰キャンセル | 腰 | False | COPY_TRANSFORMS → _dummy_腰キャンセル |
| _shadow_肩C | 上半身3 | False | COPY_TRANSFORMS → _dummy_肩C |
| _shadow_腕捩1~3 | 腕 | False | COPY_TRANSFORMS → _dummy_腕捩N |
| _shadow_手捩1~3 | ひじ | False | COPY_TRANSFORMS → _dummy_手捩N |

**parent 規則**：`_shadow_<X>` 的 parent = X 的 parent 骨。

### COPY_TRANSFORMS constraint

```
type:         COPY_TRANSFORMS
target:       自身 Armature
subtarget:    _dummy_<対応骨名>
influence:    1.0
owner_space:  POSE
target_space: POSE
```

---

## 9. IK 骨

| 骨骼 | parent | use_deform | constraint | 说明 |
|------|--------|-----------|-----------|------|
| 左足IK親 | 全ての親 | False | 无 | IK chain 根 |
| 左足ＩＫ | 左足IK親 | False | IK (target=左足首) | 足 IK |
| 左つま先ＩＫ | 左足ＩＫ | False | IK (target=左足先EX) | 足先 IK |

**要点**：
- IK 骨 parent 在全ての親下面（獨立於身体骨骼鏈）
- use_deform=False、無権重

---

## 10. XPS Helper 骨（PRESERVE）

XPS 模型特有的辅助骨、保留原始権重不做任何処理。

| 骨骼 (Inase) | parent | use_deform | 処理方式 |
|-------------|--------|-----------|---------|
| unused bip001 xtra04 | 左足 | True | PRESERVE（大腿内側 helper） |
| unused bip001 xtra02 | 右足 | True | PRESERVE（大腿内側 helper） |
| unused bip001 xtra08 | unused bip001 pelvis | True | PRESERVE（臀部 helper） |
| unused bip001 xtra08opp | unused bip001 pelvis | True | PRESERVE（臀部 helper） |
| unused bip001 pelvis | 下半身 | True | 権重 → 下半身 VG（直接映射） |
| boob left/right 1/2 | 上半身2 | True | PRESERVE（胸部 helper） |

**要点**：
- 不切権重原則：這些骨有獨特軸向和 XPS 原始権重分布、合併会喪失矯正変形
- pelvis 的 parent 必須是下半身（不是センター）、否則 xtra08 不跟下半身旋転 → 臀部撕裂

---

## 11. 骨骼显示/隐藏 (bone.hide)

纯显示層設定、不影響権重・動画・変形。PMX 的 "骨可视" flag、mmd_tools 導入時映射到 `bone.hide`。

### 規則

**付与親 slave 骨 → 隐藏**（用户不直接操作、自动跟随主骨）
**例外：D 骨 → 显示**（虽有付与親、但作为主要变形骨需要可见）

判定条件：
```python
is_slave = mmd_bone.has_additional_rotation and mmd_bone.additional_transform_bone
is_d_bone = base_name.endswith('D')  # 去掉 .L/.R 后缀
should_hide = is_slave and not is_d_bone
```

### 各骨可视状態一覧

| 骨骼 | hide | 理由 |
|------|------|------|
| 腕捩 | False | 主 twist 骨、VMD 驱動 |
| 腕捩1/2/3 | **True** | 付与親 slave (→腕捩)、自動插値 |
| 手捩 | False | 主 twist 骨、VMD 驱動 |
| 手捩1/2/3 | **True** | 付与親 slave (→手捩)、自動插値 |
| 肩C | **True** | 付与親 slave (→肩P)、自動生成 |
| 肩P | False | VMD 驱動、獨立肩控制 |
| 腰キャンセル | **True** | 付与親 slave (→腰、-1.0)、自動抵消 |
| 足D/ひざD/足首D | False | 付与親有、但 D 骨是主要変形骨 |
| 目 | False | 主変形骨 |
| _dummy_/_shadow_ | **True** | 系統骨、use_deform=False |

### 设置方式

bone.hide 在 pipeline 创建点自动设置（add_twist_bone, add_shoulder_p, complete_bones），无独立按钮/operator。

---

## 快速検査表

新建或排查骨骼時、按此表逐項驗証：

```
□ use_deform 正確？（控制骨/腰キャンセル/IK=False, 変形骨/D骨=True）
□ parent chain 正確？（参照層級図）
□ 付与親 target 正確？（D骨→主骨, 腰キャンセル→腰, 肩C→肩P）
□ TRANSFORM constraint:
    □ mix_mode_rot = ADD？（不是 AFTER）
    □ subtarget = _shadow_<骨名>？
    □ from/to rot 範囲正確？（D骨=1:1, 捩サブ=縮放, 腰キャンセル=反向）
□ _dummy_ parent = 付与親 target 骨？ use_deform=False？
□ _shadow_ parent = 本骨 parent？ use_deform=False？ 有 COPY_TRANSFORMS → _dummy_？
□ VG 権重正確？（D骨=copy主骨後清零, 控制骨=0, 指根=0, 肩P/肩C=0）
□ apply_additional_transform 調用了？（肩C + 全 _dummy_/_shadow_ 自動生成）
□ bone.hide 正確？（付与親 slave → hide=True、D 骨例外 → hide=False）
```
