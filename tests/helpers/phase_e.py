"""Phase E — VMD playback: load PMX + VMD, compare wrist drift vs target.

Sample all frames for one model into a dict, then do the same for the other,
then compute diff. Avoids the scene-switching-during-frame-iteration problem
where non-active scene frame_set may not re-evaluate the armature.
"""
import bpy


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


def _clean_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def _load_pmx_and_vmd(pmx, vmd):
    """Clean scene, import pmx + vmd. Return armature."""
    _clean_scene()
    bpy.ops.mmd_tools.import_model(filepath=pmx, scale=0.08,
                                   types={'MESH', 'ARMATURE'})
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if arm is None:
        raise RuntimeError("no armature after PMX import")
    from mmd_tools.core.model import Model
    root = Model.findRoot(arm)
    if root is None:
        raise RuntimeError("no MMD root")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.mmd_tools.import_vmd(filepath=vmd, scale=0.08)
    return arm


def _sample_bones(arm, track_bones, frames):
    """At each frame, record each tracked bone's head world position."""
    out = {}
    h = _armature_height(arm)
    for f in frames:
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        for b in track_bones:
            pos = _world_bone_loc(arm, b)
            if pos is not None:
                out.setdefault(b, {})[f] = (pos.x, pos.y, pos.z)
    return out, h


def vmd_drift(our_pmx, target_pmx, vmd_path, frames=(0, 30, 60, 120, 180)):
    """Load our+target PMX in sequence, apply same VMD, compare bone world pos."""
    # Normalize bone names to handle both 左手首 and 手首.L forms
    track_candidates = [
        ('wrist_L', ['左手首', '手首.L']),
        ('wrist_R', ['右手首', '手首.R']),
        ('ankle_L', ['左足首', '足首.L']),
        ('ankle_R', ['右足首', '足首.R']),
    ]

    # 1) Our PMX
    try:
        our_arm = _load_pmx_and_vmd(our_pmx, vmd_path)
    except Exception as e:
        return {'error': f'our PMX+VMD load failed: {e}'}
    # Resolve bone names per armature
    def resolve(arm):
        mapped = {}
        for alias, cands in track_candidates:
            for c in cands:
                if c in arm.data.bones:
                    mapped[alias] = c
                    break
        return mapped
    our_bones = resolve(our_arm)
    our_sample, our_h = _sample_bones(our_arm, list(our_bones.values()), frames)

    # 2) Target PMX (clean + reload)
    try:
        tgt_arm = _load_pmx_and_vmd(target_pmx, vmd_path)
    except Exception as e:
        return {'error': f'target PMX+VMD load failed: {e}'}
    tgt_bones = resolve(tgt_arm)
    tgt_sample, tgt_h = _sample_bones(tgt_arm, list(tgt_bones.values()), frames)

    # Compute per-bone baseline offset at frame 0, then measure drift
    # relative to baseline. This isolates dynamic (VMD-driven) error from
    # rest-pose positional difference inherent in XPS→MMD geometry mismatch.
    ref_frame = frames[0]
    baseline = {}
    for alias, _ in track_candidates:
        our_name = our_bones.get(alias)
        tgt_name = tgt_bones.get(alias)
        if not our_name or not tgt_name:
            continue
        op0 = our_sample.get(our_name, {}).get(ref_frame)
        tp0 = tgt_sample.get(tgt_name, {}).get(ref_frame)
        if op0 and tp0:
            baseline[alias] = (op0[0] - tp0[0], op0[1] - tp0[1], op0[2] - tp0[2])

    samples = []
    max_drift_ratio = 0.0
    max_wrist_ratio = 0.0
    for alias, _ in track_candidates:
        our_name = our_bones.get(alias)
        tgt_name = tgt_bones.get(alias)
        if not our_name or not tgt_name:
            continue
        bl = baseline.get(alias, (0, 0, 0))
        for f in frames:
            op = our_sample.get(our_name, {}).get(f)
            tp = tgt_sample.get(tgt_name, {}).get(f)
            if op is None or tp is None:
                continue
            dx = (op[0] - tp[0]) - bl[0]
            dy = (op[1] - tp[1]) - bl[1]
            dz = (op[2] - tp[2]) - bl[2]
            drift = (dx * dx + dy * dy + dz * dz) ** 0.5
            ratio = drift / max(our_h, tgt_h, 1e-6)
            if ratio > max_drift_ratio:
                max_drift_ratio = ratio
            if 'wrist' in alias and ratio > max_wrist_ratio:
                max_wrist_ratio = ratio
            samples.append({
                'alias': alias,
                'our_bone': our_name,
                'target_bone': tgt_name,
                'frame': f,
                'drift_m': round(drift, 4),
                'ratio': round(ratio, 4),
            })

    return {
        'n_frames': len(frames),
        'our_armature_h_m': round(our_h, 3),
        'target_armature_h_m': round(tgt_h, 3),
        'our_bone_names': our_bones,
        'target_bone_names': tgt_bones,
        'max_drift_ratio': round(max_drift_ratio, 4),
        'max_wrist_drift_ratio': round(max_wrist_ratio, 4),
        'samples_worst': sorted(samples, key=lambda s: -s['ratio'])[:10],
        'pass_gate': max_wrist_ratio < 0.05,
    }
