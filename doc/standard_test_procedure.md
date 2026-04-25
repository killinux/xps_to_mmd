# 标准测试流程

> 当用户说"测试 inase / reika / xxx"时，按这个流程跑。

## 测试目标

把 XPS 转成与目标 PMX **相同大小**的 MMD PMX，然后两者并排靠近放置，加载相同 VMD，**通过观察姿势/变形差异来评估权重质量**。

## 标准测试资产

详见 `~/.claude/projects/.../memory/reference_xps_test_assets.md`：

- **Inase** (XNA Lara)
  - XPS: `/Users/bytedance/Downloads/demo/inase (purifier)_lezisell-A/xps-b.xps`
  - 目标 PMX: `/Users/bytedance/Downloads/demo/Purifier Inase 18/Purifier Inase 18 None.pmx`
- **Reika** (DAZ G8)
  - XPS: `/Users/bytedance/Downloads/demo/Reika/xps.xps`
  - 目标 PMX: `/Users/bytedance/Downloads/demo/Reika Shimohira 2 18/Reika Shimohira 2 18 None.pmx`
- **VMD**: `/Users/bytedance/Downloads/demo/永劫无间摇香2025.2.21by小王动画/永劫无间摇香2025.2.21.vmd`

## 测试步骤

### 1. 清场景 + 清 scene 属性
```python
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)
for a in list(bpy.data.armatures): bpy.data.armatures.remove(a)
for o in list(bpy.data.objects): bpy.data.objects.remove(o)

from xps_to_mmd.properties import PREFIX
from xps_to_mmd.bone_map_and_group import mmd_bone_map
for p in mmd_bone_map:
    if hasattr(bpy.context.scene, PREFIX+p):
        setattr(bpy.context.scene, PREFIX+p, '')
```

⚠ **不要用 `bpy.ops.wm.read_factory_settings`** —— 会把 BlenderMCP 等所有 addon 卸载。

### 2. 导入 XPS（不缩放）
```python
bpy.ops.object.xps_import_xps(filepath=XPS_PATH, auto_scale=False)
```

### 3. 跑完整 pipeline
```python
bpy.ops.object.xps_auto_identify_skeleton()  # 0. 自动识别骨架

steps = [
    'object.xps_correct_bones',                # 0.5
    'object.xps_rename_to_mmd',                # 1. 重命名
    'object.xps_transfer_unused_weights',      # 1.4 转移unused（含spine middle merge）
    'object.xps_fix_forearm_bend',             # 1.5
    'object.xps_align_arms_to_canonical',      # 1.6
    'object.xps_align_fingers_to_canonical',   # 1.7
    'object.xps_complete_missing_bones',       # 2. 补全
    'object.xps_transfer_unused_weights',      # 2.5 二次清理
    'object.xps_add_mmd_ik',                   # 3. IK
    'object.xps_create_bone_group',            # 4. 骨集
    'object.xps_use_mmd_tools_convert',        # 5. mmd转换
    'object.xps_add_leg_d_bones',              # 6. D骨
    'object.xps_add_twist_bone',               # 7. 捩骨
    'object.xps_add_shoulder_p_bones',         # 8. 肩P
]
# 每步前重新拿 active armature（因为操作器会切换）
```

### 4. 缩放到目标大小

XPS 模型原生 ~1.6m，MMD 标准 ~21 单位。需要缩放 ~12.4 倍：

```python
target_height = 21.02  # 从 target PMX 量得
our_height = max(b.head_local.z for b in arm.data.bones) - min(...)
scale_factor = target_height / our_height

root = Model.findRoot(arm)
bpy.ops.object.select_all(action='DESELECT')
root.select_set(True)
bpy.ops.object.select_hierarchy(direction='CHILD', extend=True)
root.scale = (scale_factor,) * 3
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
```

### 5. 导出 PMX
```python
bpy.ops.mmd_tools.export_pmx(filepath='/Users/bytedance/Downloads/demo/<name>_auto.pmx')
```

### 6. 导入目标 PMX 并并排放置
```python
bpy.ops.mmd_tools.import_model(filepath=TARGET_PMX_PATH)

# 自动模型 X=-4，目标 X=+4（清楚分开但近距离对比，MMD 单位）
roots = [o for o in bpy.data.objects if o.type=='EMPTY' and o.mmd_type=='ROOT']
for r in roots:
    arm = next((c for c in r.children if c.type=='ARMATURE'), None)
    nb = len(arm.data.bones) if arm else 0
    r.location.x = -4.0 if nb < 200 else 4.0
```

### 7. 两边都加载相同 VMD
```python
for r in roots:
    bpy.context.view_layer.objects.active = r
    r.select_set(True)
    bpy.ops.mmd_tools.import_vmd(filepath=VMD_PATH)
```

### 8. 拖动时间轴观察差异

```python
bpy.context.scene.frame_set(80)  # 或其他动作明显的帧
```

可截图渲染对比（front view + view_selected）：
```python
bpy.ops.view3d.view_axis(type='FRONT')
bpy.ops.view3d.view_selected()
bpy.ops.render.opengl(write_still=True)
```

## 评估要点

- **姿势差异**：手臂/腿位置应该非常接近（VMD 控制的是骨骼，权重决定 mesh 跟随）
- **关节变形**：肩/肘/膝弯曲处的皮肤褶皱、拉伸是否自然
- **扭转质量**：手腕/前臂扭转时（frame 60-120）对比 twist 骨权重分布
- **躯干变形**：弯腰/转身时上半身过渡是否平滑（spine middle 合并是否正确）

## 已知差异（可接受）

- **顶点数差**：target 通常合并成 1 个 mesh（vertex 数累加），auto 是 8+ 个分散 mesh
- **face/hair 骨**：保留 XPS 原名，VMD 不驱动它们（target 也保留）
- **finger 命名**：DAZ carpal bones 已被 strip，但 middle/ring 顺序在某些模型上可能颠倒
