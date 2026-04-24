"""Phase D — Structural diff vs target PMX."""
import bpy
import math


def _load_pmx_into_temp_scene(pmx_path, scene_name):
    """Create new scene, import PMX, return (scene, armature)."""
    # Save current scene name
    cur_scene = bpy.context.window.scene
    # Create fresh scene
    new_scene = bpy.data.scenes.new(scene_name)
    bpy.context.window.scene = new_scene
    try:
        bpy.ops.mmd_tools.import_model(filepath=pmx_path, scale=0.08,
                                       types={'MESH', 'ARMATURE', 'PHYSICS'})
    except Exception as e:
        bpy.context.window.scene = cur_scene
        raise
    arm = next((o for o in new_scene.objects if o.type == 'ARMATURE'), None)
    return new_scene, arm, cur_scene


def _armature_bone_set(arm):
    return {b.name for b in arm.data.bones}


def _y_axis_of(arm, bone_name):
    b = arm.data.bones.get(bone_name)
    if not b:
        return None
    return b.matrix_local.to_3x3().col[1].normalized()


def _vg_counts(arm_scene, arm):
    """For each canonical bone, count mesh verts with weight > 0 on that vg."""
    counts = {}
    for obj in arm_scene.objects:
        if obj.type != 'MESH':
            continue
        for vg in obj.vertex_groups:
            n = 0
            for v in obj.data.vertices:
                for g in v.groups:
                    if g.group == vg.index and g.weight > 0:
                        n += 1
                        break
            counts[vg.name] = counts.get(vg.name, 0) + n
    return counts


def compare_vs_target(our_pmx, target_pmx, canonical_bones):
    """Load both into separate scenes, compute diff. Return dict."""
    cur_scene = bpy.context.window.scene

    # Ours
    our_scene = bpy.data.scenes.new("_tmp_ours")
    bpy.context.window.scene = our_scene
    try:
        bpy.ops.mmd_tools.import_model(filepath=our_pmx, scale=0.08,
                                       types={'MESH', 'ARMATURE', 'PHYSICS'})
    except Exception as e:
        bpy.context.window.scene = cur_scene
        bpy.data.scenes.remove(our_scene)
        return {'error': f'our PMX import failed: {e}'}
    our_arm = next((o for o in our_scene.objects if o.type == 'ARMATURE'), None)

    # Target
    tgt_scene = bpy.data.scenes.new("_tmp_target")
    bpy.context.window.scene = tgt_scene
    try:
        bpy.ops.mmd_tools.import_model(filepath=target_pmx, scale=0.08,
                                       types={'MESH', 'ARMATURE', 'PHYSICS'})
    except Exception as e:
        bpy.context.window.scene = cur_scene
        bpy.data.scenes.remove(our_scene)
        bpy.data.scenes.remove(tgt_scene)
        return {'error': f'target PMX import failed: {e}'}
    tgt_arm = next((o for o in tgt_scene.objects if o.type == 'ARMATURE'), None)

    if not our_arm or not tgt_arm:
        bpy.context.window.scene = cur_scene
        bpy.data.scenes.remove(our_scene)
        bpy.data.scenes.remove(tgt_scene)
        return {'error': 'no armature in one of the scenes'}

    # Bone set diff
    our_bones = _armature_bone_set(our_arm)
    tgt_bones = _armature_bone_set(tgt_arm)
    only_ours = sorted(our_bones - tgt_bones)
    only_target = sorted(tgt_bones - our_bones)

    # Core bone direction deltas
    core_dir = []
    for b in canonical_bones:
        o = _y_axis_of(our_arm, b)
        t = _y_axis_of(tgt_arm, b)
        if o is None or t is None:
            continue
        dot = max(-1.0, min(1.0, o.dot(t)))
        angle_deg = math.degrees(math.acos(dot))
        core_dir.append({'bone': b, 'angle_deg': round(angle_deg, 2)})

    # Rigid body counts by prefix
    def count_rbs(scene, key_prefix=''):
        return sum(
            1 for o in scene.objects
            if o.mmd_type == 'RIGID_BODY' and o.name.startswith(key_prefix)
        )
    our_rbs = sum(1 for o in our_scene.objects if o.mmd_type == 'RIGID_BODY')
    tgt_rbs = sum(1 for o in tgt_scene.objects if o.mmd_type == 'RIGID_BODY')
    our_jts = sum(1 for o in our_scene.objects if o.mmd_type == 'JOINT')
    tgt_jts = sum(1 for o in tgt_scene.objects if o.mmd_type == 'JOINT')

    # Vertex group count per canonical bone (ours vs target)
    # Expensive — just for CORE bones
    our_vg = _vg_counts(our_scene, our_arm)
    tgt_vg = _vg_counts(tgt_scene, tgt_arm)
    vg_diff = []
    for b in canonical_bones:
        o_n = our_vg.get(b, 0)
        t_n = tgt_vg.get(b, 0)
        if o_n > 0 or t_n > 0:
            vg_diff.append({'bone': b, 'ours': o_n, 'target': t_n,
                            'abs_diff': abs(o_n - t_n)})

    report = {
        'our_pmx': our_pmx,
        'target_pmx': target_pmx,
        'our_n_bones': len(our_bones),
        'target_n_bones': len(tgt_bones),
        'only_ours_sample': only_ours[:20],
        'only_target_sample': only_target[:20],
        'n_symmetric_diff': len(only_ours) + len(only_target),
        'core_bone_dir_delta_deg': sorted(core_dir, key=lambda x: -x['angle_deg']),
        'rb_counts': {'ours': our_rbs, 'target': tgt_rbs},
        'joint_counts': {'ours': our_jts, 'target': tgt_jts},
        'vg_count_top_diffs': sorted(vg_diff, key=lambda x: -x['abs_diff'])[:15],
    }

    # Cleanup: restore scene, remove temps
    bpy.context.window.scene = cur_scene
    bpy.data.scenes.remove(our_scene)
    bpy.data.scenes.remove(tgt_scene)

    return report
