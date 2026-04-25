# 通用 XPS→PMX 转换方案

> 当前系统只支持 Inase (XNA Lara) 预设，目标是支持任意 XPS 模型自动转换。

## 当前架构（iter-36, HEAD `b290729`）

### Pipeline 步骤
```
1.4  transfer_unused_weights — 跳过 SKIP_PATTERNS，处理控制骨
1.5  fix_forearm / align_arms / align_fingers — L1 rest pose 对齐
2    complete_bones — 补全 MMD 骨（全ての親/センター/腰/下半身/上半身3/IK/D骨）
2.5  transfer_unused_weights 二次 — 清理全ての親 + pelvis→下半身 + 上半身/下半身校正
3    IK — 足IK/つま先IK + 膝旋转限制
4    bone_group — 骨骼分组
5    mmd_convert — mmd_tools 转换
6    d_bones — 足D/ひざD/足首D + additional_transform
7    twist — 位置扫描 rename + VG swap + 渐变分割 + 约束
8    shoulder_p — 肩P/肩C
8.5  apply_additional_transform
9-11 physics — body/hair/breast rigid body
```

### 已通用的部分
- **Twist scanner**: 纯位置扫描，不依赖骨名，自动找 arm segment 上的候选骨
- **渐变分割**: PMXEditor 风格双骨线性插值，按 t 位置分配
- **VG swap**: 只在 rename 候选被消费时触发（有/无候选自动适配）
- **物理系统**: 基于 MMD 标准骨名匹配
- **Phase ABCDE 测试**: 通用验证框架

### 依赖 preset/硬编码的部分
- **骨名映射** (`presets/xna_lara_Inase.json`): XPS 骨名 → MMD 骨名
- **SKIP_PATTERNS**: `('foretwist', 'pelvis', 'xtra08', 'xtra04', 'xtra02', 'xtra07', 'muscle')`
- **pelvis_patterns**: `('pelvis',)` → 下半身 direct rename
- **CONTROL_BONES**: `('全ての親', 'センター', 'グルーブ')`

## 通用化方案

### 第 1 步：自动骨架识别器

不依赖骨名，纯靠拓扑 + 几何位置推断骨骼角色。

#### 算法
1. **找根骨**: Z 最低的骨（或无 parent 的骨）
2. **找 spine 链**: 从根骨沿 Z 向上走，找最长的直链（root→hips→spine→chest→neck→head）
3. **找 arm/leg 分叉**: spine 链上的分叉点，Z 高的是 arm（肩），Z 低的是 leg（足）
4. **用对称性区分 L/R**: X > 0 vs X < 0
5. **找 hand/foot**: arm/leg 链的末端
6. **找 finger**: hand 的子骨链

#### 输出
```python
{
    "hips": "bone_name",           # → 下半身 候选
    "spine": ["bone1", "bone2"],   # → 上半身/上半身2
    "chest": "bone_name",          # → 上半身2/上半身3
    "neck": "bone_name",           # → 首
    "head": "bone_name",           # → 頭
    "shoulder_L": "bone_name",     # → 左肩
    "upper_arm_L": "bone_name",    # → 左腕
    "forearm_L": "bone_name",      # → 左ひじ
    "hand_L": "bone_name",         # → 左手首
    "thigh_L": "bone_name",        # → 左足
    "shin_L": "bone_name",         # → 左ひざ
    "foot_L": "bone_name",         # → 左足首
    # ... R 侧镜像
}
```

#### 参考
- Blender 的 `rigify` 自动识别器
- Mixamo 的骨架映射算法
- Convert_to_MMD_claude 的 preset 系统本质上是手动版

### 第 2 步：通用 helper 骨分类器

扫描所有非标准骨（不在自动识别结果中的骨），按位置分类：

```
对每个 non-standard bone:
  1. 计算它在哪个 body segment 上（投影到 arm/leg/spine 段）
  2. 按 parent 关系确认归属
  3. 分类:
     - spine_area (上半身附近) → PRESERVE（如 boob/breast helper）
     - hip_area (下半身附近, parent=hips) → 下半身 direct
     - upper_arm segment → twist scanner 候选
     - forearm segment → twist scanner 候选
     - thigh (parent=thigh) → PRESERVE (如 xtra04)
     - hip_helper (parent=pelvis) → PRESERVE + reparent to 下半身 (如 xtra08)
     - muscle/elbow → twist scanner 候选
     - leaf bone (no children, no weights) → 忽略
```

### 第 3 步：验证反馈环

转换后自动跑 Phase A-D（不需要 target PMX 和 VMD），输出质量报告：

```
Phase A: 骨骼完整性（必需骨是否存在）
Phase B: PMX round-trip（export + reimport 骨骼数/dangling joints）
Phase C: 物理 bake（有物理时）
Phase D-lite: 自检（骨骼方向合理性、VG 覆盖率）
```

## XPS 模型的常见骨架格式

### XNA Lara (Inase, Reika 等)
```
骨名格式: "arm right shoulder", "leg left thigh", "bip001 xtra07"
特点: 有 xtra 系列辅助骨, pelvis 独立, foretwist 在前臂
典型骨数: 90-120
```

### DAZ Genesis 8 (一些 Koikatsu/HS 转换模型)
```
骨名格式: "lShldrBend", "lForearmBend", "lThighBend", "lThighTwist"
特点: 有 ThighTwist/ForearmTwist, 无 xtra 系列, Carpal 骨在手腕附近
典型骨数: 70-90
```

### 通用 biped (一些老 XPS)
```
骨名格式: "Bip001 L UpperArm", "Bip001 R Thigh"
特点: 最简结构, 很少有辅助骨
典型骨数: 50-70
```

## 踩坑记录（跨模型通用）

### 七条硬规则（见 doc/hip_butt_thigh_weight_guide.md）
1. 永远不手动编辑单顶点权重
2. 永远不把 helper 骨合并到主变形骨
3. 永远不用绝对阈值删下半身权重
4. 永远不把 pelvis helper reparent 到腰
5. 永远不用 proximity-based weight transfer 处理 twist
6. 永远不把 vertex count 差异当 bug
7. 永远不跳诊断层级 L4→L1→L2→L3

### Twist 系统要点
- 位置扫描不依赖骨名（已实现）
- 边界骨去重：t≈0 优先分给 START 端的段
- 排除逻辑：只排除有手指子骨的兄弟，不是所有有子骨的兄弟
- VG swap 只在 rename 候选时触发
- 渐变分割是独立步骤，5 anchor 双骨线性插值
- 肩端/肘端 dead zone t<0.05 保护关节过渡

### 权重处理要点
- pelvis → 下半身 直接 rename（不做 per-vertex-nearest）
- 全ての親 → per-vertex nearest 到最近变形骨（头发区域→頭）
- 上半身/下半身 head 重合 → Z 坐标判断校正
- helper 骨 PRESERVE + parent-chain 继承（不合并到主骨）
- 腋窝平滑：肩→腕 additive 权重（src_keep_floor=1.0）
- unused pelvis reparent 到 下半身（让 xtra08 跟随下半身旋转）
- 首.parent=上半身3 需要二次 pass（dict 顺序 bug）

### PMX 属性要点
- additional_transform: 腕捩1/2/3 influence 0.25/0.50/0.75
- 肩C: influence -1.0（cancel）
- D骨: influence 1.0（copy）
- 足IK chain=2, つま先IK chain=1
- ひざ LIMIT_ROTATION x=[0, 180°]
- mmd_bone 属性必须设置才能 PMX round-trip 保留
