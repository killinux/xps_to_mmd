# Twist 权重渐变分割实现计划

> iter-33 之后的下一步。当前 twist 系统只有骨骼级付与（系统1），缺顶点级渐变（系统2）。

## 现状

### 已完成
- 位置扫描 + rename：xtra07pp→腕捩、muscle_elbow→手捩（XPS 原始权重零损失保留）
- VG swap：腕↔腕捩（纠正覆盖区域）
- 付与属性：腕捩1/2/3 additional_transform_influence = 0.25/0.50/0.75
- 腋窝平滑：肩→腕 additive 权重
- arm chain use_connect=False

### 缺失
- 腕捩1/2/3、手捩1/2/3 的 **vertex group 权重全是 0**
- Target 有 541/739/371 verts 在这些 VG 上
- 没有沿臂段的 twist 渐变分割

## 目标

实现 PMXEditor 风格的双骨线性插值，把腕/ひじ的权重沿段位置分配到 5 个 anchor 骨上。

## 算法

### 上臂段（腕→ひじ）

5 个 anchor：
```
t=0.00  腕      (0% twist)
t=0.25  腕捩1   (25% twist)
t=0.50  腕捩2   (50% twist)
t=0.75  腕捩3   (75% twist)
t=1.00  腕捩    (100% twist, main)
```

### 前臂段（ひじ→手首）

5 个 anchor：
```
t=0.00  ひじ    (0% twist)
t=0.25  手捩1   (25% twist)
t=0.50  手捩2   (50% twist)
t=0.75  手捩3   (75% twist)
t=1.00  手捩    (100% twist, main)
```

### 每个顶点的处理

1. 计算顶点在段上的投影 t：`t = dot(vertex - seg_from, seg_dir) / |seg_dir|²`
2. clamp t 到 [0, 1]
3. **死区**：t < 0.05（肩端）或 t < 0.05（肘端）→ 不处理，留在原骨上
4. 找相邻两个 anchor `(t_lo, bone_lo)` 和 `(t_hi, bone_hi)`
5. 计算插值比：`k = (t - t_lo) / (t_hi - t_lo)`
6. 分配权重：
   - `bone_lo += original_weight * (1 - k)`
   - `bone_hi += original_weight * k`
7. 从原骨（腕/ひじ）移除该权重

### 关键约束

- **只分割腕/ひじ的权重**，不动已有的腕捩/手捩权重（从 xtra07pp rename 来的）
- 总权重不变（分割不是切割）
- 肩端死区 t<0.05 保护肩-腕 BDEF2 过渡
- 对称处理 L/R

## 实现位置

在 `add_twist_bone_operator.py` 的 `OBJECT_OT_add_twist_bone` 类中：
- 在 Phase 4（VG swap）之后，添加 Phase 5（gradient split）
- 或者作为独立 operator，在 pipeline 最后可选执行

参考：`/opt/mywork/Convert_to_MMD_claude/operators/twist_operator.py` lines 457-619

## 验证

1. 跑 iter-34，确认腕捩1/2/3 有权重
2. 对比 target 的分布（每 0.1 t 的平均权重）
3. 加载 VMD 看手臂扭转效果
4. Phase E drift 不应退步

## 风险

- 渐变分割是对腕/ひじ权重的重新分配，如果 anchor 位置或死区参数不对，可能影响肩/肘关节变形
- Convert_to_MMD_claude 已验证此算法在 Inase + Reika 上都通过，风险可控
