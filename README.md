# xps_to_mmd

Blender 3.6 插件：自动将 XPS (XNA Lara) 模型转换为 MMD (MikuMikuDance) 格式。

无需手动映射骨骼、无需参考 PMX 模型，一键完成从 XPS 导入到 PMX 导出的全流程。

## 安装

### 前置依赖

- Blender 3.6
- [XPS Tools](https://github.com/johnzero7/XNALaraMesh)（XPS 模型导入）
- [mmd_tools](https://extensions.blender.org/add-ons/mmd-tools/)（MMD 格式转换/导出）

### 安装步骤

1. 下载本仓库为 ZIP 或 clone 到 Blender 插件目录：
   ```
   # macOS
   ~/Library/Application Support/Blender/3.6/scripts/addons/xps_to_mmd/
   # Linux
   ~/.config/blender/3.6/scripts/addons/xps_to_mmd/
   # Windows
   %APPDATA%\Blender Foundation\Blender\3.6\scripts\addons\xps_to_mmd\
   ```
2. Blender → 编辑 → 偏好设置 → 插件 → 搜索 `xps_to_mmd` → 启用
3. 3D 视口侧边栏（N 面板）出现 `xps_to_mmd` 标签

## 使用方法

### 一键转换（推荐）

1. 点击面板顶部 **"0. 导入 XPS"** 导入 XPS 模型
2. 选中导入的骨架（Armature）
3. 点击 **"一键转换 XPS→MMD"**
4. 等待 ~2 秒，16 步自动完成

转换完成后可直接用 mmd_tools 导出 PMX。

### 面板说明

面板分两个选项卡：

#### 主骨骼管理

| 区域 | 说明 |
|------|------|
| 导入 XPS | 调用 XPS Tools 导入 |
| 一键转换 | 全自动 pipeline（推荐） |
| 预设 / Auto / Check | 骨骼映射预设管理，Auto 自动识别骨骼角色 |
| 骨骼映射面板 | 显示 XPS→MMD 骨骼对应关系，可手动调整 |
| 步骤 1~5 | 手动分步执行（调试用） |

#### 次标准骨骼管理

| 区域 | 说明 |
|------|------|
| 次标准骨骼 | D 骨、捩骨、肩P 骨的手动添加（一键转换已包含） |
| 物理 | 刚体/头发/胸部物理生成（需先跑完主流水线） |
| XPS 专属修正 | L1 rest pose 对齐、L3 权重交换等诊断工具 |
| 通用工具 | 清理无权重骨骼、导出骨骼信息 |

### Pipeline 步骤详解

一键转换内部执行以下 16 步：

```
Step 0     自动识别骨架        skeleton_identifier 拓扑+几何检测骨骼角色
Step 0.5   归正骨架位置        设置原点、清除动画
Step 1     重命名为 MMD       XPS 骨名 → MMD 标准名（含 VG 同步 rename）
Step 1.4   转移权重 (第一次)    pelvis→下半身 直接映射，unused helper 权重转移
Step 1.5   修正前腕弯曲        L1 rest pose 对齐
Step 1.6   对齐上臂            L1 rest pose 对齐
Step 1.7   对齐手指            L1 rest pose 对齐
Step 2     补全缺失骨骼        创建控制骨、中间脊柱骨、指根骨
Step 2.5   清理控制骨权重       第二次 transfer，清零控制骨残留权重
Step 3     添加 MMD IK        腿部 IK 链
Step 4     创建骨骼集合         骨骼组（センター/体上/腕/指/体下/足/IK）
Step 5     mmd_tools 转换     调用 mmd_tools 转换为 MMD 模型结构
Step 5.5   VG 残留清理         合并旧名 VG（D 骨 copy 前必须完成）
Step 6     添加腿部 D 骨       足D/ひざD/足首D + TRANSFORM 约束 (ADD)
Step 7     添加捩骨            腕捩/手捩 + gradient split 权重分配
Step 8     添加肩P骨           肩P/肩C
Step 8.5   apply_transform    展开付与親为 _dummy_/_shadow_/TRANSFORM 三件套
```

## 实现原理

### 核心思想

**保留 XPS 的权重，重建 MMD 的骨骼结构。**

XPS 模型的顶点权重是游戏美术师精心调过的，直接复用比重新计算效果更好。Pipeline 的主要工作是：
- 识别 XPS 骨骼角色（拓扑+几何，不依赖骨名）
- 重命名骨骼和 VG 为 MMD 标准名
- 创建 MMD 特有的控制骨/D 骨/捩骨/IK
- 设置付与親约束系统

### 骨骼识别 (skeleton_identifier)

纯拓扑+几何方法，不依赖骨名：

1. **脊柱链检测**：从最高的中心双侧骨向下追 parent chain
2. **分叉点检测**：找到手臂/腿部 L/R 分叉（subtree depth >= 3）
3. **脊柱映射**：分叉之间的骨 → 上半身/上半身1/上半身2
4. **手臂链追踪**：分叉 → 肩/上臂/前臂/手 + 手指识别
5. **腿部链追踪**：分叉 → 大腿/膝/足/足先
6. **眼骨检测**：头部子骨中的最高对称对

已验证：XNA Lara (Inase)、DAZ Genesis 8、Bip001 (3ds Max)。

### 权重处理策略

| 策略 | 适用场景 | 说明 |
|------|---------|------|
| Rename | 源骨存在（如 spine middle → 上半身1） | 最优，保留原始权重 |
| Direct mapping | pelvis → 下半身 | VG 直接合并 |
| Per-vertex-nearest | unused helper 骨 | 按顶点位置找最近变形骨 |
| Split | 源骨不存在（如上半身3、首1） | Fallback，线性插值 |
| Preserve | XPS helper（xtra04/02/08、boob） | 不动，保留原始矫正变形 |

### 付与親 (additional_transform) 系统

MMD 的骨骼联动核心。在 Blender 中通过三件套模拟：

```
目标骨旋转 → _dummy_(parent chain) → _shadow_(COPY_TRANSFORMS) → 本骨(TRANSFORM, ADD)
```

| 骨 | 付与親 target | influence | 说明 |
|---|---|---|---|
| 足D/ひざD/足首D | 足/ひざ/足首 | 1.0 | D 骨完全复制 |
| 腰キャンセル | 腰 | -1.0 | 反向抵消腰旋转 |
| 肩C | 肩P | 1.0 | 肩联动 |
| 腕捩1/2/3 | 腕捩 | 0.25/0.50/0.75 | 分段 twist |
| 手捩1/2/3 | 手捩 | 0.25/0.50/0.75 | 分段 twist |

骨骼显示规则：付与親 slave 骨自动隐藏（用户不直接操作），D 骨例外（主变形骨需可见）。

## 项目结构

```
xps_to_mmd/
├── __init__.py                    # 插件注册入口
├── skeleton_identifier.py         # 拓扑+几何骨骼角色识别
├── helper_classifier.py           # 非标准骨分类 (twist/pelvis/preserve/merge)
├── bone_map_and_group.py          # XPS→MMD 骨名映射 + 骨骼组定义
├── bone_utils.py                  # 骨骼工具函数
├── properties.py                  # Scene 属性注册
├── ui_panel.py                    # N 面板 UI
├── operators/
│   ├── one_click_operator.py      # 一键转换 pipeline
│   ├── auto_identify_operator.py  # Auto 识别按钮
│   ├── rename_bones_operator.py   # Step 1: 重命名
│   ├── complete_bones_operator.py # Step 2: 补全骨骼 + _split_chain_weights
│   ├── xps_fixes_operator.py      # Step 1.4/2.5: 权重转移 + L1 对齐
│   ├── add_leg_d_bones_operator.py    # Step 6: D 骨
│   ├── add_twist_bone_operator.py     # Step 7: 捩骨
│   ├── add_shoulder_p_bones_operator.py # Step 8: 肩P
│   ├── ik_operator.py             # Step 3: IK
│   ├── collection_operator.py     # Step 4: 骨骼组
│   └── physics_operator.py        # 物理（刚体/头发/胸部）
├── tests/
│   ├── test_skeleton_identifier.py    # 骨骼识别离线测试
│   └── test_helper_classifier.py      # 分类器离线测试
├── doc/
│   ├── mmd_bone_spec.md           # MMD 骨骼完整规格（11 节 + 检查表）
│   ├── TODO.md                    # 问题记录 + 版本变更
│   ├── architecture_retrospective.md  # 架构回顾与重写指南
│   ├── standard_test_procedure.md     # 标准测试流程
│   └── hip_butt_thigh_weight_guide.md # 腰/臀/大腿权重指南
└── presets/                       # 骨骼映射预设 JSON
```

## 当前状态 (v1.8)

- Pipeline: 16/16 步成功，~2 秒
- 骨骼: 188 骨（172 显示 + 16 隐藏）
- 验证: Inase VMD frame 80/120/200 姿态匹配
- 测试: skeleton_identifier 3 模型通过，helper_classifier 19 项通过

## TODO

### 已知限制

- 肩左右不对称（腋窝 smooth 引入，左 1688 vs 右 636 verts）
- 胸部骨未映射为 MMD 标准名（boob → 乳奶）
- 面部表情骨未映射（QQ 系列）
- 仅在 Inase (XNA Lara) 上完整验证，DAZ/Bip001 待验证 pipeline

### 重构计划

当前 pipeline 是单线程串行执行，步骤间有隐式状态依赖（VG/bone 名字、parent chain、分类结果）。
理想架构应分为 4 个独立 Phase，每层有明确的输入/输出契约：

```
Phase 0: 分析（只读）
  → 输出 conversion_plan.json（骨骼映射+分类+权重报告，可 review）

Phase 1: 权重保全（只动 VG，不动骨）
  → pelvis 独立 operator，不嵌在 transfer 里
  → VG rename 和 bone rename 完全分离

Phase 2: 骨骼重建（建骨+设 parent，不动权重）
  → 有源骨时 rename 保留原始权重，没有才 split

Phase 3: 约束系统
  → D 骨/捩骨/肩P/IK + apply_additional_transform

Phase 4: 自动验证（只读，无需 target PMX）
  → 基于 mmd_bone_spec.md 的规则引擎自检
  → 下半身 >= 6000? D 骨有权重? 控制骨 = 0? mix_mode = ADD?
```

**泛化目标**：任意 XPS humanoid 模型，无需 target PMX 参考，Phase 4 质量报告全绿。

详见 `doc/architecture_retrospective.md`。

## 参考文档

- `doc/mmd_bone_spec.md` — MMD 骨骼完整规格（parent/deform/constraint/付与親/显示规则）
- `doc/architecture_retrospective.md` — 项目架构回顾与重写指南（15 个踩坑记录）
- `doc/TODO.md` — 问题追踪 + 版本变更历史 (v1.3→v1.8)

## License

MIT
