"""Phase E — VMD playback: load PMX + VMD, compare wrist drift vs target."""
import bpy


def _load_vmd(vmd_path, armature, scale=0.08):
    """mmd_tools.import_vmd into the armature's root."""
    from mmd_tools.core.model import Model
    root = Model.findRoot(armature)
    if root is None:
        raise RuntimeError("no MMD root")
    # Select root for import
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    try:
        bpy.ops.mmd_tools.import_vmd(filepath=vmd_path, scale=scale,
                                     bone_mapper='PMX',
                                     use_pose_mode=False)
    except TypeError:
        # older mmd_tools might not accept bone_mapper
        bpy.ops.mmd_tools.import_vmd(filepath=vmd_path)


def _world_bone_loc(arm, bone_name):
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return None
    return arm.matrix_world @ pb.head


def _armature_height(arm):
    zs = [((arm.matrix_world @ b.head_local).z) for b in arm.data.bones]
    if not zs:
        return 1.0
    return max(zs) - min(zs)


def vmd_drift(our_pmx, target_pmx, vmd_path, frames=(0, 30, 60, 120, 180)):
    """Load our+target PMX in separate scenes, apply same VMD, compare bone world pos."""
    cur_scene = bpy.context.window.scene

    def load_pair(pmx):
        s = bpy.data.scenes.new(f"_tmp_{hash(pmx) % 10000}")
        bpy.context.window.scene = s
        bpy.ops.mmd_tools.import_model(filepath=pmx, scale=0.08,
                                       types={'MESH', 'ARMATURE'})
        arm = next((o for o in s.objects if o.type == 'ARMATURE'), None)
        return s, arm

    try:
        our_scene, our_arm = load_pair(our_pmx)
        _load_vmd(vmd_path, our_arm)
    except Exception as e:
        bpy.context.window.scene = cur_scene
        return {'error': f'our PMX/VMD load failed: {e}'}

    try:
        tgt_scene, tgt_arm = load_pair(target_pmx)
        _load_vmd(vmd_path, tgt_arm)
    except Exception as e:
        bpy.context.window.scene = cur_scene
        bpy.data.scenes.remove(our_scene)
        return {'error': f'target PMX/VMD load failed: {e}'}

    our_h = _armature_height(our_arm)
    tgt_h = _armature_height(tgt_arm)

    track_bones = ['左手首', '右手首', '左足首', '右足首']
    samples = []
    max_drift_ratio = 0.0
    for f in frames:
        # ours
        bpy.context.window.scene = our_scene
        our_scene.frame_set(f)
        for o in our_scene.objects:
            o.update_tag(refresh={'OBJECT'})
        bpy.context.view_layer.update()
        ours_pos = {b: _world_bone_loc(our_arm, b) for b in track_bones}
        # target
        bpy.context.window.scene = tgt_scene
        tgt_scene.frame_set(f)
        for o in tgt_scene.objects:
            o.update_tag(refresh={'OBJECT'})
        bpy.context.view_layer.update()
        tgt_pos = {b: _world_bone_loc(tgt_arm, b) for b in track_bones}

        for b in track_bones:
            op = ours_pos.get(b)
            tp = tgt_pos.get(b)
            if op is None or tp is None:
                continue
            drift = (op - tp).length
            ratio = drift / max(our_h, tgt_h, 1e-6)
            if ratio > max_drift_ratio:
                max_drift_ratio = ratio
            samples.append({
                'frame': f, 'bone': b,
                'drift_m': round(drift, 4),
                'ratio': round(ratio, 4),
            })

    # Cleanup
    bpy.context.window.scene = cur_scene
    bpy.data.scenes.remove(our_scene)
    bpy.data.scenes.remove(tgt_scene)

    wrist_samples = [s for s in samples if '手首' in s['bone']]
    max_wrist_ratio = max((s['ratio'] for s in wrist_samples), default=0.0)

    return {
        'n_frames': len(frames),
        'our_armature_h_m': round(our_h, 3),
        'target_armature_h_m': round(tgt_h, 3),
        'max_drift_ratio': round(max_drift_ratio, 4),
        'max_wrist_drift_ratio': round(max_wrist_ratio, 4),
        'samples_worst': sorted(samples, key=lambda s: -s['ratio'])[:10],
        'pass_gate': max_wrist_ratio < 0.05,
    }
