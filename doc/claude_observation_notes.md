# Claude session observation notes

> 记录 Codex 旁路观察 Claude session 时发现的可疑点。
> 只记录风险和待验证项，不代表已经确认是代码 bug。
> 观察对象: `/root/.claude/projects/-opt-mywork-bl/649df81b-377f-45eb-895b-c7c9beb38080.jsonl`
> 更新时间: 2026-04-25 16:39 UTC

## 2026-04-25 16:31-16:36: 骨骼显示/隐藏逻辑反复变更

### 现象

Claude 先新增了 `object.xps_fix_bone_visibility` operator，随后发现它会把 `unused bip001 xtra02` 等 helper 骨 unhide，导致用户看到异常大的 helper 骨。之后又提交了两次修正：

- `5520169 Fix visibility operator: only hide slaves, don't unhide helpers`
- `88f37c1 Move bone.hide to creation point, remove standalone visibility operator`

当前 HEAD 已移除 standalone operator 和 UI 按钮，改为在创建 twist/shoulder/waist-cancel 相关骨时直接设置 `bone.hide=True`。

### 我认为有问题的地方

1. 文档没有同步到最终实现。
   - `doc/TODO.md` 仍写着“新增骨骼显示修复按钮”。
   - `doc/mmd_bone_spec.md` 仍写着 Panel 里有 `"修正骨骼显示/隐藏"` 按钮。
   - `doc/architecture_retrospective.md` 仍把 `fix_visibility` 写成 pipeline phase 3.6。
   - 这些和 HEAD `88f37c1` 的“remove standalone visibility operator”矛盾。

2. `operators/xps_fixes_operator.py` 留下了无意义代码：
   - 当前有 `_CLASSES = _CLASSES + ()`。
   - 不会直接破坏运行，但说明删除 operator 时清理不完整。

3. “主动隐藏”从后处理 operator 移到了创建点，本质仍然是主动设置 `bone.hide=True`。
   - 用户明确说“还是不要有主动隐藏和显示的逻辑”。
   - Claude 的最终实现只是不再提供按钮，但仍在创建 `腕捩1/2/3`、`手捩1/2/3`、`肩C`、`腰キャンセル` 时主动隐藏。
   - 如果用户的真实意思是“不自动改任何 hide 状态”，当前实现并没有满足。

### 建议验证

- 先和用户确认目标策略：
  - 策略 A: 按 MMD 标准自动隐藏付与親 slave。
  - 策略 B: 不自动改 `bone.hide`，只提供报告。
  - 策略 C: 只隐藏 mmd_tools/PMX 标准导入后本来会隐藏的骨，不碰 XPS helper。
- 如果保留策略 A，需要把文档从“按钮/operator”改为“创建点设置 hide”。
- 如果采用策略 B，需要移除创建点的 `bone.hide=True`，并保留只读检查脚本或报告。

## 2026-04-25 16:36: Claude 判断“188 骨，172 显示，16 隐藏，正常”

### 现象

Claude 重新跑 pipeline 后检查隐藏列表：

```text
总骨骼: 188, 显示: 172, 隐藏: 16
隐藏:
  左/右手捩1,2,3
  左/右腕捩1,2,3
  左/右肩C
  腰キャンセル.L/R
```

Claude 结论：“隐藏的全部是付与親 slave 骨，其他骨全部可见。正常了。”

### 我认为有问题的地方

1. 只检查了隐藏列表，没有检查“应该隐藏但未隐藏”和“应该显示但未显示”的完整期望表。
   - 例如 D 骨是否全部可见，只能从“未出现在隐藏列表”间接推断。
   - 没有验证 `bone.hide` 和 `pose.bone.mmd_bone.additional_transform_bone` 的对应关系。

2. 188 骨和现有文档里的 189 不一致。
   - `doc/TODO.md` v1.7 写“总骨骼 189”。
   - 当前测试输出是 188。
   - 需要明确是统计口径变化、某个骨被移除，还是之前文档写错。

3. “正常”只基于骨骼显示数，不等于姿态/权重正常。
   - 用户的问题来自“看到的骨骼很少”和视觉异常。
   - 需要截图或至少记录目标/auto 的 visible bone diff、pose diff、关键 VG 数量。

### 建议验证

- 加一个只读检查，输出这些项目：
  - 标准骨总数和缺失列表。
  - 每个 `has_additional_rotation` 骨的 `bone.hide`、target、influence、是否 D 骨例外。
  - D 骨全部可见。
  - XPS preserve helper 是否保持原有 hide 状态。
- 更新文档里的总骨数，或说明为什么 Inase 当前是 188。

## 2026-04-25 16:38: Inase 测试只到“场景准备好”

### 现象

Claude 根据用户“测一下inase，知道怎么测吧”执行：

- export `/Users/bytedance/Downloads/demo/inase_auto_v18.pmx`
- 清场
- reimport auto PMX
- import target PMX
- 给两个 armature 导入同一个 VMD
- `frame_set(80)`
- 输出 `Frame 80 ready`

### 我认为有问题的地方

1. 当前只证明命令执行成功，没有记录姿态对比结论。
   - 没有截图。
   - 没有关键骨位置/旋转 diff。
   - 没有 mesh 裂痕、下半身、足D、上半身边界等之前高风险点的检查。

2. 测试脚本里 `auto_root` 选择逻辑取第一个带 `mmd_root.name` 的 EMPTY。
   - 如果 Blender 场景里残留多个 MMD root，可能选错。
   - 虽然脚本后面会清场，但 export 前是在现有场景里选 root，风险在 export 前。

3. 测试把 `space.overlay.show_bones = False`，这适合看 mesh 姿态，但不适合回答“骨骼很少/隐藏是否正常”的问题。
   - 如果用户正在验证骨显示问题，应该另存一个骨显示视图或单独输出骨可见性报告。

### 建议验证

- frame 80 后至少补三类输出：
  - 截图或 viewport 状态，auto 和 target 并排。
  - 关键骨/关键 VG 检查：下半身、足D、足、上半身/上半身1/上半身2/上半身3、首/首1。
  - hide 状态报告，尤其是 D 骨和 preserve helper。

## 2026-04-25 16:40: v1.8 tag 在 README 更新前创建

### 现象

用户要求：“目前是个可用的版本，标记一下，push上去，然后把readme补一下，面板的使用，代码实现原理，todo，以及重构计划”。

Claude 先执行：

```text
git tag v1.8
git push origin v1.8
```

随后才开始读取/准备更新 README。

### 我认为有问题的地方

1. 如果 `v1.8` tag 只表示“当前代码可用版本”，这个顺序可以接受。
2. 如果 `v1.8` tag 期望包含 README、面板说明、实现原理、TODO、重构计划，则 tag 已经过早创建。
3. README 更新之后如果还要纳入 `v1.8`，需要移动 tag；但移动远端 tag 会影响已拉取的人，必须明确确认。

### 建议验证

- 确认 `v1.8` 的语义：
  - 只标代码可用点：不要移动 tag。
  - 要包含 README 文档：需要删除/重建本地和远端 `v1.8`，或者另打 `v1.8-docs` / `v1.8.1`。

## 2026-04-25 16:49: 物理/表情调研并行 agent 已启动，结果未整合

### 现象

Claude 针对“刚体物理、衣服、PMXEditor、mmd_tools、历史 Convert_to_MMD、远端记忆、表情、path D、互联网最佳实现”启动了多个异步 agent：

- Convert_to_MMD_claude physics/morph 历史调研
- mmd_tools physics/morph API 调研
- 当前/远端 memory 调研
- Web research PMXEditor physics/morphs

### 我认为有问题的地方

1. 目前只是启动 agent，还没有整合结论。
2. 调研范围很大，容易把“社区经验/猜测”和“项目已验证事实”混在一起。
3. 涉及互联网资料时，最终文档需要保留来源链接或至少区分“本项目经验”“mmd_tools 源码/API”“PMXEditor/PMX 规范”“网上经验”。
4. 远端 `18.224.30.14` 的记忆如果无法访问，最终文档必须明确说明，不应该假装已经读取。

### 建议验证

- 最终调研文档按来源分层：
  - 本项目当前实现。
  - Convert_to_MMD_claude 历史实现和踩坑。
  - mmd_tools 实际 API。
  - PMXEditor/PMX 原理。
  - 互联网资料。
- 对 “path D 可用、其他方式不可用” 单独列证据：测试条件、失败方式、可复现命令或文件。

### 16:51 补充观察

已有 3/4 agent 完成，Claude 表示“等最后一个（互联网调研）返回后开始写文档和实现”。

其中 mmd_tools API 调研结果里有大量“Signature (from usage patterns)”形式的推断，例如 `Model.createRigidBody(...)`、`Model.createJoint(...)` 参数签名。这些不能直接当作 mmd_tools 官方 API 或稳定接口写进设计文档。

我本地搜索 `/opt/mywork` 没找到 mmd_tools 源码文件，当前证据主要来自本项目 `operators/physics_operator.py` 的调用方式。因此后续如果 Claude 写“mmd_tools API 是……”应要求它明确：

- 是从源码确认，还是从项目现有调用推断。
- 本机是否实际找到并读取了 mmd_tools 源码。
- 如果没找到源码，只能写“本项目当前用法”，不能写成完整 API surface。

另一个设计风险：`physics_operator.py` 里现有参数是固定经验值，例如 `DEFAULT_MASS = 1.0`、`DEFAULT_DAMP = 0.5`、`JOINT_ROT_LIMIT_DEG = 10.0`、`BREAST_SPRING_ANGULAR = 2000.0`。如果 Claude 后续直接扩展衣服/裙子物理，但仍沿用这些固定参数，没有按骨链长度、模型尺度、碰撞组、层级深度做参数化，就是高风险实现。

### 16:57 补充观察

Claude 说“4/7 调研完成”，并计划等 3 个追加 agent 后“开始写文档和实现”。说明调研范围已经从最初 4 个 agent 扩到 7 个。

我认为需要特别防的点：

1. 范围膨胀。
   - 用户要求的是调研文档 + 刚体/物理部分尝试实现 + 表情只写设计文档。
   - 如果 Claude 同时做 PmxTailor、morph 自动化、衣服、头发、胸部、反向 joint、Reika 测试，容易变成半成品。

2. 互联网参数不可直接硬编码。
   - 调研结果里出现 hair/skirt/breast 的具体 mass/damping/spring 推荐值。
   - 这些来源多是教程经验，不一定适配当前模型尺度、Blender Bullet、mmd_tools 导出路径。
   - 设计文档可以列为候选 baseline；实现必须有可配置 preset 和测试报告，不能写死为唯一方案。

3. “Path D”解释出现歧义。
   - 互联网 agent 结果把 Path D 解释成 `/tests/helpers/phase_d.py` structural diff。
   - 但用户之前说“path D 是可用的，其他方式为什么不可用”，很可能指历史 morph transfer 路线中的 Path D，不一定是当前测试 helper 的 Phase D。
   - Claude 后续文档如果把 Path D 定义错，会直接误导表情设计。

4. 追加调研使用 web 资料时必须保留来源和置信度。
   - DeviantArt、LearnMMD、Scribd、个人博客适合经验参考，但不应等同 PMX 规范或 mmd_tools 源码。
   - 最终报告需要标明“规范事实 / 源码事实 / 项目验证事实 / 社区经验”。

## 2026-04-25 16:42: README commit `57f477f` 的问题

### 现象

Claude 提交了：

```text
57f477f doc: comprehensive README with usage, architecture, TODO, and rewrite plan
```

README 从 1 行扩展到 228 行。

### 我认为有问题的地方

1. README 声称“当前状态 (v1.8)”，但 `v1.8` tag 并不指向 README commit。
   - `v1.8` = `88f37c1`
   - `HEAD` = `57f477f`
   - `git tag --points-at HEAD` 为空
   - 所以 README 不是 `v1.8` tag 的一部分。

2. README 第 5 行声称“无需参考 PMX 模型”，但第 189 行又写“仅在 Inase 上完整验证，DAZ/Bip001 待验证 pipeline”。
   - 这属于产品能力过度声明。
   - 更准确的表述应该是“目标是无需参考 PMX；当前 Inase 完整验证，其他 rig 仍需验证”。

3. README 第 179 行写“Inase VMD frame 80/120/200 姿态匹配”，证据不足。
   - 我观察到的 Claude 测试只输出了 `Frame 80 ready`。
   - 没看到 frame 120/200 的执行记录。
   - 没看到截图、pose diff、关键骨 transform diff、mesh 变形检查或报告文件。
   - 这个结论不应该写成已验证事实，至少应降级为“frame 80 场景已准备，待人工/截图确认”。

4. README 第 180 行写“helper_classifier 19 项通过”，实际 `tests/test_helper_classifier.py` 是一个测试函数，内部 expected 19 个分类项。
   - 这可以说“19 个 mock 分类断言”，不应让人误解为 19 个真实模型/真实场景测试。
   - skeleton_identifier “3 模型通过”也是 mock/offline 构造树，不等于真实 DAZ/Bip001 pipeline 通过。

5. README 第 65 行写“一键转换内部执行以下 16 步”，但列出来包含 Step 5.5，实际列表是 17 个编号项。
   - Claude 之前输出“一键转换完成: 16/16”，但 README 的列表包含 0、0.5、1、1.4、1.5、1.6、1.7、2、2.5、3、4、5、5.5、6、7、8、8.5。
   - 需要统一“执行计数”和“文档步骤计数”。

6. README 第 138 行写“付与親 slave 骨自动隐藏”，这仍然和用户“不要有主动隐藏和显示逻辑”的原始担忧冲突。
   - 如果最终决定保留自动隐藏，应明确这是 MMD 标准行为。
   - 如果最终决定不主动改 hide，README 需要改。

### 建议验证

- README 的“已验证”内容只写有证据的结果。
- 把“目标能力”和“当前能力”分开。
- 明确 `v1.8` tag 是否需要包含 README；如果不移动 tag，README 应避免说自己就是 v1.8 tag 内容。
- 对 mock tests 和真实 Blender pipeline tests 分开描述。

## 当前应优先处理

1. 先决定 `bone.hide` 策略，避免继续在“自动隐藏”和“不要主动隐藏”之间来回改。
2. 同步文档，尤其是删除 operator 后仍残留的按钮/pipeline 描述。
3. 把 Inase 测试从“Frame ready”补成可判断的结果报告。
4. 确认 `v1.8` tag 是否需要包含 README；如果需要，不要让 Claude 直接移动远端 tag，先确认影响。
