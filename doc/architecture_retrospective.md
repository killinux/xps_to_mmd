# XPS→MMD 项目架构回顾与重写指南

> 本文档总结了 v1.0→v1.8 全部踩坑经验和架构思考。
> 目标：下次重写时，照着这份文档走，不重复踩坑。
> 最后更新: 2026-04-25 (v1.8, HEAD c70aa62)

---

## 一、核心原理

XPS 和 MMD 的骨骼体系有根本性差异：

```
XPS (游戏提取):                      MMD (动画驱动):
├─ 扁平命名 (spine lower/middle)     ├─ 严格层级 (上半身→上半身1→上半身2→上半身3)
├─ 所有骨都有权重                     ├─ 控制骨零权重 (センター/腰/腰キャンセル)
├─ 无 IK/约束                        ├─ IK 链 + 付与親约束系统
├─ helper 骨散布 (foretwist/xtra)     ├─ D骨+捩骨 精确分工
└─ 无标准化                          └─ PMX 规范严格定义每根骨的角色
```

转换的本质是：**保留 XPS 的权重（艺术家精心调过的），重建 MMD 的骨骼结构（层级/约束/付与親）**。

### 黄金规则

1. **不切权重** — XPS 原始权重是最优解，split/merge 会引入边界不连续
2. **有源骨时 rename，没有才 create** — spine middle 存在就 rename 为上半身1，不存在才 split
3. **先 VG 后 bone** — Blender armature modifier 按名字关联，VG 必须先就位
4. **控制骨 use_deform=False** — 防止 per-vertex-nearest 把权重分到控制骨上
5. **D 骨 mix_mode=ADD** — 不是 AFTER，AFTER 在本地空间做乘法会累积误差

---

## 二、MMD 标准骨骼体系

```
全ての親 (root, control, deform=False)
  └─ センター (center, control, deform=False)
     └─ グルーブ (groove, control, deform=False)
        └─ 腰 (waist, control, deform=False)
           ├─ 上半身 → 上半身1 → 上半身2 → 上半身3 → 首 → 首1 → 頭
           │   ├─ 肩P → 肩 → [肩C] → 腕 → 腕捩 → ひじ → 手捩 → 手首
           │   │                                                  ├─ 人指０→１→２→３
           │   │                                                  ├─ 中指０→１→２→３
           │   │                                                  ├─ 薬指０→１→２→３
           │   │                                                  ├─ 小指０→１→２→３
           │   │                                                  └─ 親指０→１→２
           │   └─ (右側同構造)
           └─ 下半身
                ├─ 腰キャンセル.L → 左足 → 左ひざ → 左足首 → 左足先EX
                │                  左足D → 左ひざD → 左足首D  (D骨)
                └─ 腰キャンセル.R → (右側同構造)
  ├─ 左足IK親 → 左足ＩＫ → 左つま先ＩＫ
  └─ 右足IK親 → 右足ＩＫ → 右つま先ＩＫ
```

### 骨骼四大类

| 类型 | use_deform | 权重 | 约束 | 典型骨 |
|------|-----------|------|------|--------|
| 控制骨 | False | 0 | 无 | 全ての親, センター, 腰, 腰キャンセル |
| 主变形骨 | True | XPS原始 | 无 | 上半身, 首, 腕, 足 |
| D骨 | True | copy主骨后清零 | TRANSFORM(ADD) | 足D, ひざD, 足首D |
| 付与親 slave | True | 0~gradient | TRANSFORM(ADD) | 腕捩1/2/3, 手捩1/2/3, 肩C |

### 付与親 (additional_transform) 系统

MMD 的骨骼联动核心。Blender 中通过 _dummy_/_shadow_/TRANSFORM 三件套模拟：

```
目标骨旋转 → _dummy_(parent chain继承) → _shadow_(COPY_TRANSFORMS) → 本骨(TRANSFORM, ADD)
```

**显示规则**：`has_additional_rotation + transform_bone → hide`，D 骨例外（用户需要看到）。

详见 `doc/mmd_bone_spec.md`。

---

## 三、踩过的所有坑

### A. 时序依赖类（最致命）

| # | 坑 | 版本 | 根因 | 修复 |
|---|---|------|------|------|
| 1 | pelvis VG 时序 | v1.3 | 下半身骨还不存在时就需要 VG | 先建 VG 再建骨，Blender 会自动关联 |
| 2 | pelvis early return | v1.8 | 无 merge 骨时提前 return 跳过 pelvis 代码 | pelvis 处理独立于 unused 转移，去掉 early return |
| 3 | VG rename 顺序 | v1.4 | 先 rename bone 后 rename VG，1410 verts 悬空 | 先 VG 后 bone |
| 4 | VG cleanup 在 D 骨之后 | v1.6 | 旧名 VG 没合并就被 D 骨 copy | cleanup 移到 step 5.5（D 骨之前） |

**通用教训**：pipeline 每一步的前置条件必须显式声明。VG/bone 名字同步是脆弱的全局状态。

### B. 权重处理类

| # | 坑 | 版本 | 根因 | 修复 |
|---|---|------|------|------|
| 5 | 上半身裂痕 | v1.5→v1.8 | `_split_chain_weights` 线性插值边界不连续 | 有源骨时 rename 保留原始权重，没有才 split |
| 6 | foretwist 被 transfer 吃掉 | v1.5 | step 1.4 把 twist 候选骨的权重散掉 | SKIP_PATTERNS 白名单 |
| 7 | xtra helper 被合并 | 早期 | 合并后失去大腿/臀部矫正变形 | PRESERVE 白名单 |
| 8 | ひじ=0 误判为 bug | v1.6 | XPS 源模型 elbow 本来就没权重 | 先查源模型再定性 |
| 9 | 上半身/下半身 head 重合 | v1.3 | per-vertex-nearest 无法区分同位骨 | Z 轴校正：z < spine.head → 下半身 |

**通用教训**：XPS 原始权重是最优解。`_split_chain_weights` 是 fallback，不是首选。

### C. 约束/属性类

| # | 坑 | 版本 | 根因 | 修复 |
|---|---|------|------|------|
| 10 | D 骨 mix_mode AFTER | v1.5 | AFTER 在本地空间做乘法，微小误差累积 | 改 ADD（纯加法，MMD 标准） |
| 11 | 腰キャンセル 付与親→下半身 | 早期 | reimport 时叠加下半身旋转导致 IK 抖 | target = 腰（祖父），不是下半身（父） |
| 12 | _dummy_/_shadow_ use_deform=True | v1.5 | 辅助骨参与变形 | 改 False |

**通用教训**：MMD 约束系统微妙。ADD vs AFTER、付与親 target 的祖父/父选择，都是 PMX 规范的硬性要求。

### D. 分类/识别类

| # | 坑 | 版本 | 根因 | 修复 |
|---|---|------|------|------|
| 13 | spine middle 被分类为 merge | v1.8 | helper_classifier 不知道它是上半身1 | skeleton_identifier 优先识别 |
| 14 | pelvis reparent 后被误分类 | v1.8 | step 2 改 parent 后 step 2.5 auto-classifier 不认识了 | 不依赖跨步骤的分类结果 |
| 15 | 硬编码 preset 无法泛化 | v1.0 | xna_lara_Inase.json 只能做一个模型 | 拓扑+几何识别 > 名字匹配 |

**通用教训**：分类结果不能跨步骤复用（parent 改了分类就变了）。识别应在 pipeline 最前端一次性完成。

---

## 四、下半身/pelvis 反复出问题的专题

这个问题出现了 3 次（v1.3、v1.8 两次），有结构性弱点。

**根因模式**：`transfer_unused_weights` 有两条 pelvis 路径：
1. 正确路径：pelvis→下半身 direct mapping（直接 ADD 到下半身 VG）
2. 错误路径：pelvis 走 per-vertex-nearest（散到足D/ひざD 等附近骨）

**触发条件**：
- early return 在 pelvis 代码之前
- step 2 把 pelvis reparent 到下半身 → step 2.5 不再识别
- 任何导致第一次 transfer pass 为空的改动

**重写时方案**：pelvis→下半身 必须是独立 operator，不嵌在 transfer 里。

**快速验证**：pipeline 跑完后检查 `下半身 >= 6000 verts`。

---

## 五、理想架构（重写方案）

### 设计原则

```
1. 识别层（只读）→ 2. 权重层（保守处理）→ 3. 结构层（建骨/约束）→ 4. 验证层（自检）
每层有明确的输入/输出契约，不允许跨层状态依赖
```

### Pipeline 设计

```
Phase 0: 分析（只读，不改任何东西）
  0.1  skeleton_identifier    → bone_role_map {xps_name: mmd_role}
  0.2  helper_classifier      → helper_map {xps_name: preserve|twist|pelvis|merge}
  0.3  weight_audit           → vg_report {bone: vert_count, coverage}
  输出: conversion_plan.json（完整计划，可 review/override）

Phase 1: 权重保全（只动 VG，不动骨）
  1.1  rename_vgs             → XPS VG 名 → MMD VG 名
  1.2  pelvis_to_lower_body   → pelvis VG → 下半身 VG（独立 operator）
  1.3  transfer_unused        → unused 前缀骨 VG → per-vertex-nearest
  1.4  z_boundary_correct     → 上半身/下半身 Z 校正
  输出: 所有 VG 就位，名字正确

Phase 2: 骨骼重建（建骨+设 parent，不动权重）
  2.1  rename_bones           → XPS bone 名 → MMD bone 名
  2.2  create_control_bones   → 全ての親/センター/グルーブ/腰/腰キャンセル
  2.3  complete_spine          → 上半身1/上半身3/首1（源骨不存在时才 split）
  2.4  create_finger_roots    → 指根骨 pass-through
  2.5  align_rest_pose        → L1 方向对齐
  输出: 完整 MMD 骨骼层级

Phase 3: 约束系统（不动骨位置）
  3.1  create_d_bones         → D 骨 + copy VG + clear 主骨 VG
  3.2  create_twist_bones     → 捩骨 + gradient split
  3.3  create_shoulder_p      → 肩P/肩C
  3.4  create_ik              → IK 链
  3.5  mmd_tools_convert      → apply_additional_transform
  3.6  (visibility)            → bone.hide 在各创建点 (3.1~3.3) 自动设置，非独立后处理步骤
  输出: 完整 MMD 模型

Phase 4: 验证（只读）
  4.1  bone_completeness      → 标准骨是否齐全
  4.2  weight_sanity          → 下半身>=6000? D骨有权重? 控制骨=0?
  4.3  constraint_check       → D骨 mix=ADD? 付与親 target 正确?
  4.4  parent_chain_check     → 对照 mmd_bone_spec.md
  输出: quality_report（Pass/Fail + 具体项）
```

### 与当前架构的关键差异

**1. Phase 0 的 conversion_plan**

当前：边分析边改，出错后难回溯。
改进：先生成完整计划（JSON），可 review/override，然后一次性执行。
好处：
- 错了可以从 plan 重来，不需要 reimport XPS
- 不同模型可以保存/复用 plan
- 调试时能看到"它打算做什么"

**2. VG 和 bone rename 完全分离**

当前：rename_bones_operator 同时改 VG 和 bone，时序耦合。
改进：Phase 1 只改 VG，Phase 2 才改 bone。通过 `bone_role_map` 关联。

**3. pelvis 独立 operator**

当前：嵌在 transfer_unused_weights 里，被 early return/分类变化反复搞坏。
改进：`pelvis_to_lower_body` 独立步骤，只做一件事。

**4. Phase 4 自动验证（无 target 也能跑）**

当前：需要 target PMX 对比。
改进：基于 mmd_bone_spec.md 的规则引擎自检：

```python
checks = [
    ("下半身 >= 6000 verts", lambda: vg_count("下半身") >= 6000),
    ("足D > 0 verts",        lambda: vg_count("左足D") > 0),
    ("足 = 0 verts",         lambda: vg_count("左足") == 0),
    ("控制骨 = 0",           lambda: all(vg_count(b) == 0 for b in CONTROL_BONES)),
    ("D骨 mix=ADD",          lambda: all(c.mix_mode_rot == 'ADD' for c in d_constraints)),
    ("腰キャンセル target=腰", lambda: pb.mmd_bone.additional_transform_bone == "腰"),
]
```

---

## 六、实现"任意 XPS 无 target 也能转"的路线

### 已完成

- skeleton_identifier（拓扑+几何，Inase/DAZ/Bip001 通过）
- helper_classifier（twist/pelvis/preserve/merge 自动分类）
- 完整 pipeline（16 步，2s）
- mmd_bone_spec.md（完整 MMD 骨骼规格）

### 还需要

**1. 泛化 helper_classifier（中等工作量）**
- 当前用 mapped ancestor + 位置判断，对 Inase 准确
- 需要在 3+ 不同 XPS 模型上验证（DAZ G8、Bip001、Unity humanoid）
- 可能需要 segment proximity fallback

**2. spine chain 自适应（小工作量）**
- 当前：2 段 → upper_body + upper_body1
- 需要：3+ 段（DAZ 有 4 段 spine）
- 方案：spine_seg[0] → upper_body，spine_seg[-1] → upper_body1，中间段 merge 到最近邻

**3. 自检验证器（中等工作量）**
- Phase 4 的 quality_report
- 基于 mmd_bone_spec.md 的规则引擎
- 不需要 target PMX

**4. 多模型测试集（持续）**
- Inase (XNA Lara) ✓
- Reika (DAZ G8) — 结构通过，finger swap 待修
- Bip001 (3ds Max) — skeleton_identifier 通过，pipeline 待测
- 还需要：Unity humanoid、Mixamo rig

### 最终目标

```
bpy.ops.object.xps_one_click_convert()
→ Phase 4 quality_report: 45/45 PASS
→ 无需 target PMX 参考
→ 任意 XPS humanoid 模型
```

---

## 七、诊断协议（遇到问题时必查）

**按此顺序排查，不要跳步**：

1. **查行业最优方案** — WebSearch: MMD 社区、PMX 规范、PMXEditor 教程
2. **查 mmd_tools 怎么做的** — 优先复用，不重造轮子
3. **查 PMXEditor/nanoem 源码** — 开源参考实现
4. **不切权重** — 用 PRESERVE 或 per-vertex-nearest，不手动改 VG
5. **查 Convert_to_MMD_claude 踩坑** — `doc/` 下有半年的 playbook/pitfalls

**遇到"权重不对"的姿态偏差时，严格按此排查**：
1. 方向偏差？→ 查 rest pose bone direction
2. 旋转行为不对？→ 查 constraints、lock_rotation
3. 控制范围不对？→ 查 VG 顶点数对比
4. 以上都排除后才考虑权重 → 优先数学方法，不手动调

---

## 八、关键文件索引

| 文件 | 用途 |
|------|------|
| `doc/mmd_bone_spec.md` | MMD 骨骼完整规格（层级/parent/deform/constraint/付与親/显示） |
| `doc/TODO.md` | 所有问题记录 + 版本变更 + scale 踩坑 |
| `doc/hip_butt_thigh_weight_guide.md` | 腰/臀/大腿权重 9 个坑 |
| `doc/standard_test_procedure.md` | 标准测试流程（VMD 并排对比） |
| `skeleton_identifier.py` | 拓扑+几何骨骼角色识别 |
| `helper_classifier.py` | 非标准骨分类（twist/pelvis/preserve/merge） |
| `operators/one_click_operator.py` | pipeline 步骤定义 |
| `operators/xps_fixes_operator.py` | transfer/pelvis/visibility 等修正 |
| `operators/complete_bones_operator.py` | 补全缺失骨 + `_split_chain_weights` |
| `bone_map_and_group.py` | XPS→MMD 骨名映射 + 骨骼组 |

### 远端参考

```
ssh root@18.224.30.14
/root/.claude/projects/-opt-mywork-mytest-bl/memory/   — 更早期的 memory
/opt/mywork/Convert_to_MMD_claude/doc/                 — 半年踩坑文档
```

---

## 九、版本历史速查

| 版本 | 核心改动 |
|------|---------|
| v1.3 | pelvis VG 时序修复 (482→6797) |
| v1.4 | 一键转换、VG rename 顺序、Panel 重构 |
| v1.5 | D骨 ADD、上半身1 split、STANDARD_MMD_BONES 白名单、捩 additive |
| v1.6 | 首1 split、VG cleanup 移到 5.5、足D 修复 |
| v1.7 | 指根骨 8 个 pass-through |
| v1.8 | spine middle rename、pelvis early return 修复、骨骼显示修复 |
