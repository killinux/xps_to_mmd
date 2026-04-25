# XPS→MMD 待修复项

## 权重问题

### [已解决] ~~ひじ 权重 = 0~~
- **日期**: 2026-04-25 发现，2026-04-25 排查完成
- **结论**: XPS 源模型 `arm left elbow` 骨在 body mesh 上**从导入开始就没有权重**（BEFORE pipeline: NONE）。前臂区域权重全在 foretwist/xtra07 等 helper 骨上。Target 的 ひじ=1611 是 Convert_to_MMD 额外创建的权重，非 XPS 复用。按"不切权重"原则不修。

### [已修复] ~~足D 权重过少 (275 → 581/871)~~
- **日期**: 2026-04-25 发现，v1.6 修复
- **修复**: VG cleanup 从 step 9 移到 step 5.5（D 骨之前），旧名 VG 先合入再 copy 到 D 骨

### [已修复] ~~足 残留 306/596 → 0~~
- **日期**: 2026-04-25 发现，v1.6 修复
- **修复**: 同上，cleanup 时序调整后 D 骨 copy+clear 正确清零足 VG

## 骨骼结构

### [低] 指根骨缺失 (人指０/中指０/薬指０/小指０)
- **日期**: 2026-04-25 确认
- **现象**: target 有指根骨 (各 ~1000 verts, parent=手首)，auto 的指骨直接 parent=手首
- **根因**: XPS 没有 carpal 骨，需要新建+从手首 split 权重
- **备注**: 涉及权重切分，按"不切权重"原则暂不实现。后续如有需要再讨论

### [低] 肩/腕捩/手捩 左右不対称
- **日期**: 2026-04-25 确认
- **现象**: 肩 左 1710 vs 右 589 (2.9x)，腕捩/手捩 也有 2x+ 不対称
- **根因**: 腋窝 `_split_chain_weights` 左 1688 vs 右 636 verts (2.66x)，源于 body mesh 几何微妙差异
- **修复方向**: 可加対称性修正 (mirror 左→右或均值化)，但可能对非対称模型引入误差

## 功能增强

### [中] 首1 骨缺失
- **日期**: 2026-04-25 发现
- **现象**: target 有首1 (2595 verts, parent=首)，位于首と頭之间
- **修复方向**: 类似上半身1，用 `_split_chain_weights` 从首 split

### [已修复] ~~上半身/上半身2 边界权重裂痕~~
- **日期**: 2026-04-25 发现，2026-04-25 修复
- **修复**: spine middle → 上半身1 在 step 1 rename（保留 XPS 原始权重），不再用 `_split_chain_weights` 重建

### [已修复] ~~spine middle → 上半身1 直接 rename~~
- **日期**: 2026-04-25 尝试+回退，2026-04-25 正确实现
- **修复**: skeleton_identifier 检测 spine chain 有 2+ 段时识别第二段为 `upper_body1_bone`，bone_map 加 `upper_body1_bone → 上半身1`。Step 1 rename 后 step 1.4 不再散掉（STANDARD_MMD_BONES 保护），step 2 检测到已存在只修正 parent 链

### [低] 胸部骨骼映射 (boob → 乳奶)
- **日期**: 2026-04-25 发现
- **现象**: auto 用 `boob left/right 1/2` (XPS 原名)，target 用 `乳奶.L/.R`
- **修复方向**: 在 rename_to_mmd 中加映射，或在 helper_classifier 中识别

### [低] 面部表情骨 (QQ 系列)
- **日期**: 2026-04-25 发现
- **现象**: target 有 QQ1~QQ36 等面部骨 (~500 verts each)，auto 用 XPS 原名
- **修复方向**: 需要 XPS→MMD 面部骨映射表

---

## 已修复记录

| 日期 | 版本 | 问题 | 修复 |
|------|------|------|------|
| 2026-04-25 | v1.3 | pelvis VG 时序 bug (下半身 482→6797) | xps_fixes_operator: 去掉 bone 存在性检查 |
| 2026-04-25 | v1.4 | VG rename 失败 (1410 verts 悬空) | rename_bones: 先 rename VG 再 rename bone |
| 2026-04-25 | v1.4 | one_click VG cleanup map 失效 | 保存 XPS→MMD map 在 rename 前 |
| 2026-04-25 | v1.5 | D 骨 mix_mode AFTER | add_leg_d/add_twist: AFTER → ADD |
| 2026-04-25 | v1.5 | 上半身1 缺失 | complete_bones: 新建+split (5842 verts) |
| 2026-04-25 | v1.5 | 上半身1 被 transfer 吃掉 | xps_fixes: STANDARD_MMD_BONES 白名单 |
| 2026-04-25 | v1.5 | D 骨 VG 用 rename 不用 copy | add_leg_d: 改为 copy+clear |
| 2026-04-25 | v1.5 | 捩 _dummy_/_shadow_ use_deform=True | add_twist: 改 False |
| 2026-04-25 | v1.5 | ひじ gradient split 消费源权重 | add_twist: ひじ→手首 改 additive |
| 2026-04-25 | v1.6 | 首1 缺失 | complete_bones: 新建+split (1134 verts) |
| 2026-04-25 | v1.6 | VG cleanup 在 D骨之后跑 | one_click: cleanup 移到 step 5.5 |
| 2026-04-25 | v1.6 | 足 残留 306/596 + 足D 275 | 足D: 581/871, 足: 0/0 |
| 2026-04-25 | v1.6 | ひじ=0 排查 | 确认 XPS 源模型特征，非 bug |
| 2026-04-25 | v1.7 | 指根骨缺失 | complete_bones: 人指０/中指０/薬指０/小指０ pass-through |
| 2026-04-25 | v1.8 | 上半身/上半身2 边界裂痕 | spine middle→上半身1 在 step 1 rename, 保留 XPS 原始权重 |
| 2026-04-25 | v1.8 | pelvis→下半身 被 early return 跳过 | transfer_unused_weights 去掉 early return |
| 2026-04-25 | v1.8 | 骨骼显示/隐藏不符 MMD 标准 | bone.hide 在创建点设置 (add_twist_bone, add_shoulder_p, complete_bones)，付与親 slave→hide, D骨例外 |

## 版本变更概要

### v1.3 (2026-04-25)
- pelvis→下半身 VG 时序 bug 修复 (下半身 482→6797 verts)
- 踩坑文档 `hip_butt_thigh_weight_guide.md` 重写

### v1.4 (2026-04-25)
- 一键转换按钮 (17 步全自动, ~2s)
- VG rename: 先 rename VG 再 rename bone
- one_click VG cleanup
- Panel 重构

### v1.5 (2026-04-25)
- D 骨 TRANSFORM mix_mode: AFTER→ADD
- D 骨 VG: rename→copy+clear
- 上半身1 新建+split (5842 verts)
- STANDARD_MMD_BONES 白名单
- 捩 _dummy_/_shadow_ use_deform=False
- ひじ→手首 gradient split 改 additive

### v1.6 (2026-04-25)
- 首1 新建+split (1134 verts)
- VG cleanup 移到 step 5.5 (D 骨之前)
- 足D/足残留修复

### v1.7 (2026-04-25)
- 指根骨 8 个 (pass-through, 不切権重)
- 总骨骼 189 (v1.3 时 179)。注：v1.8 pipeline 产出 188 骨（移除 standalone visibility operator 后统计口径变化）

### v1.8 (2026-04-25)
- spine middle → 上半身1 在 step 1 rename，保留 XPS 原始権重 (4574 verts)
- 修复上半身/上半身2 边界 mesh 裂痕
- skeleton_identifier 新增 upper_body1_bone 检测
- 修复 pelvis→下半身 direct mapping 被 early return 跳过 (下半身 539→6892)
- bone.hide 在创建点自动设置 (add_twist_bone, add_shoulder_p, complete_bones)，付与親 slave→hide, D骨例外 (见 mmd_bone_spec.md §11)

## Scale 踩坑记录

**問題**: `bpy.ops.object.transform_apply(scale=True)` 在 MMD 模型上不稳定。

**原因**: MMD 模型结构 `Empty(ROOT) → Armature → Mesh` + backup armature + rigidbody/joint 对象。
Blender 3.6 的 transform_apply 在这种复杂层级下经常静默失败（scale 不归 1，bone data 不变）。

**正确做法（稳定可靠）**: 导出 PMX 再 reimport。PMX 导出时 mmd_tools 会自动应用 root.scale，
reimport 后 scale 自然是 1:1。

```python
# 设 scale
root.scale = (scale_factor,) * 3

# 导出（mmd_tools 自动应用 scale）
bpy.ops.mmd_tools.export_pmx(filepath='path/to/auto.pmx')

# 如需并排对比：reimport
bpy.ops.mmd_tools.import_model(filepath='path/to/auto.pmx')
```

**不要**反复尝试 `transform_apply` — 浪费时间且结果不可靠。
