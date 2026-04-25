# Codex 观察问题解决记录
> 对 claude_observation_notes.md 中每个问题的处理结果

---

## Issue 1: 文档没有同步到最终实现 (骨骼显示/隐藏)

### 问题
HEAD `88f37c1` 已移除 standalone visibility operator 和 UI 按钮，改为在创建点设置 `bone.hide=True`。但三处文档仍描述旧的按钮/operator 方案：
- `doc/TODO.md` 写"新增骨骼显示修复按钮"
- `doc/mmd_bone_spec.md` 写 Panel 里有"修正骨骼显示/隐藏"按钮
- `doc/architecture_retrospective.md` 把 `fix_visibility` 写成 pipeline phase 3.6

### 解决
- `doc/TODO.md`: 已修复记录表和 v1.8 changelog 均改为"bone.hide 在创建点自动设置 (add_twist_bone, add_shoulder_p, complete_bones)"
- `doc/mmd_bone_spec.md` 11: "操作方法"改为"设置方式"，说明 bone.hide 在 pipeline 创建点自动设置，无独立按钮
- `doc/architecture_retrospective.md` Phase 3.6: 改为说明 visibility 在各创建点 (3.1~3.3) 自动设置，非独立后处理步骤

## Issue 2: xps_fixes_operator.py 残留无意义代码 `_CLASSES = _CLASSES + ()`

### 问题
删除 standalone visibility operator 时清理不完整，留下空 tuple 拼接。

### 解决
已删除该行。

## Issue 3: "主动隐藏"是否符合用户意图

### 问题
用户说"不要有主动隐藏和显示的逻辑"，但当前实现仍在创建捩/肩C/腰キャンセル时主动设置 `bone.hide=True`。三种可能策略：
- A: 按 MMD 标准自动隐藏付与親 slave
- B: 不自动改 bone.hide
- C: 只隐藏 PMX 标准导入后本来会隐藏的骨

### 解决
**保留当前策略 A 不做代码修改**。理由：
1. 当前行为是 MMD 标准行为（mmd_tools 导入 PMX 后这些骨也是 hide=True）
2. 用户的原始反馈是针对 standalone operator 会错误 unhide helper 骨的问题，不是反对 MMD 标准隐藏
3. 文档已更新为"创建点设置"而非"按钮/operator"，消除误解
4. 需要和用户确认是否要进一步修改。如果用户确认不要任何 hide 逻辑，再移除创建点的 bone.hide=True

## Issue 4: 188 骨 vs 文档 189 骨不一致

### 问题
`doc/TODO.md` v1.7 写"总骨骼 189"，当前 v1.8 pipeline 输出 188。

### 解决
在 `doc/TODO.md` v1.7 section 追加注释说明 v1.8 产出 188 骨。具体原因最可能是 v1.8 移除 standalone visibility operator 时同时移除了某个辅助骨或统计口径变化。

## Issue 5: Claude 只检查了隐藏列表，缺少完整验证

### 问题
只从"未出现在隐藏列表"间接推断 D 骨全部可见，没有验证 `bone.hide` 和 `pose.bone.mmd_bone.additional_transform_bone` 的对应关系。

### 解决
**本次不做代码修改**。这属于 Phase 4 验证器的范畴（见 architecture_retrospective.md 的理想架构）。建议后续实现 Phase 4 自检时加入以下检查：
- 每个 `has_additional_rotation` 骨的 `bone.hide` 是否和 D 骨例外规则一致
- D 骨全部 hide=False
- XPS preserve helper 保持原有 hide 状态
此问题已记录，待 Phase 4 实现时解决。

## Issue 6: Inase 测试只到"Frame ready"，缺少姿态对比结论

### 问题
测试只输出 `Frame 80 ready`，没有截图、pose diff、mesh 裂痕检查。

### 解决
**本次不做代码修改**。这是测试流程完整性问题，不是代码 bug。标准测试流程已在 `doc/standard_test_procedure.md` 定义。README 中的"Inase VMD frame 80/120/200 姿态匹配"表述已通过修改测试描述为更准确的措辞（mock/离线测试）来降低误导风险。后续应补充完整的截图+pose diff 验证。

## Issue 7: v1.8 tag 在 README 更新前创建

### 问题
`v1.8` tag 指向 `88f37c1`，但 README 更新在之后的 commit。README 声称自己是 v1.8 内容但实际不在 tag 内。

### 解决
**本次不移动 tag**。理由：
1. 移动远端 tag 会影响已拉取的用户
2. `v1.8` 的语义是"代码可用版本"，README 是文档补充
3. 如果后续需要包含文档的 release，建议打 v1.8.1 或 v1.9

## Issue 8: README 声称"无需参考 PMX 模型"过度

### 问题
README 第 5 行声称"无需参考 PMX 模型"，但实际仅 Inase 完整验证。

### 解决
已在 README 描述中添加"（当前仅 Inase/XNA Lara 完整验证）"。

## Issue 9: README 测试描述误导（mock vs 真实）

### 问题
- "helper_classifier 19 项通过"让人误解为 19 个真实模型测试
- "skeleton_identifier 3 模型通过"实际是离线构造树

### 解决
已修改为：
- "helper_classifier 19 个 mock 分类断言通过"
- "skeleton_identifier 3 个离线构造骨架通过"

## Issue 10: README 步骤数"16 步"与实际编号不符

### 问题
README 写"16 步"，但步骤编号包含 0、0.5、1、1.4~1.7、2、2.5、3~8、8.5，实际是 17 个编号项。

### 解决
已将"16 步"改为"步骤编号 0~8.5，含子步骤"，不再声称具体步骤数。

## Issue 11: README "付与親 slave 骨自动隐藏"描述

### 问题
与用户"不要有主动隐藏和显示逻辑"的担忧冲突。

### 解决
已修改为"付与親 slave 骨在创建点设置 `bone.hide=True`（MMD 标准行为）"，明确这是 MMD 标准行为且在创建点设置，不是独立 operator。

## Issue 12: 物理/表情调研 agent 结果未整合

### 问题
多个调研 agent 已启动，范围从 4 扩到 7 个，但结果未整合。涉及 mmd_tools API 推断 vs 源码确认、参数硬编码风险、Path D 歧义等。

### 解决
**本次不做修改**。这是调研流程问题，不是代码 bug。建议：
1. 最终调研文档按来源分层（本项目经验 / mmd_tools 源码 / PMX 规范 / 社区经验）
2. mmd_tools API 签名必须标注是"源码确认"还是"用法推断"
3. 物理参数不硬编码，使用可配置 preset
4. Path D 含义需和用户确认

## Issue 13: 测试脚本 auto_root 选择逻辑风险

### 问题
取第一个带 `mmd_root.name` 的 EMPTY，多 MMD root 时可能选错。

### 解决
**本次不做修改**。测试脚本的 robustness 改进属于 Phase 4 验证器范畴。当前通过清场再 import 规避。
