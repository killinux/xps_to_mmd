"""Phase C — Physics bake + quantitative tip delta on hair/breast."""
import bpy
from mathutils import Vector


def _world_tail_of_rigid(rb_obj, arm_obj):
    """Get current world location of the bone.tail associated with a rigid body."""
    bone_name = rb_obj.mmd_rigid.bone
    if not bone_name or bone_name not in arm_obj.pose.bones:
        return None
    pb = arm_obj.pose.bones[bone_name]
    return arm_obj.matrix_world @ pb.tail


def bake_and_measure(frames=(1, 120), prefix_map=None):
    """Bake physics cache across frames, measure tip delta per prefix group.

    Returns {
      'prefix_name': {
        'n_rigids': int,
        'tip_delta_max_m': float,     # max of per-rigid |tip@frame_max - tip@frame_min|
        'tip_delta_mean_m': float,
        'samples': [{name, delta}]
      }
    }"""
    if prefix_map is None:
        prefix_map = {
            'body': 'auto_rb_body_',
            'hair': 'auto_rb_hair_',
            'breast': 'auto_rb_breast_',
        }

    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if not arm:
        return {'error': 'no armature'}

    # Free previous point cache then bake
    for ps in bpy.data.particles:  # no-op usually but clean
        pass
    try:
        # Free then bake all physics
        bpy.ops.ptcache.free_bake_all()
    except Exception:
        pass
    try:
        bpy.context.scene.frame_start = min(frames)
        bpy.context.scene.frame_end = max(frames)
        bpy.ops.ptcache.bake_all(bake=True)
    except Exception as e:
        return {'error': f'bake failed: {e}'}

    # Sample frame positions
    results = {}
    for group, prefix in prefix_map.items():
        rbs = [o for o in bpy.data.objects
               if o.mmd_type == 'RIGID_BODY' and o.name.startswith(prefix)]
        if not rbs:
            results[group] = {'n_rigids': 0, 'tip_delta_max_m': 0.0,
                              'tip_delta_mean_m': 0.0, 'samples': []}
            continue

        positions = {}  # rb_name -> {frame: Vec}
        for f in frames:
            bpy.context.scene.frame_set(f)
            bpy.context.view_layer.update()
            for rb in rbs:
                positions.setdefault(rb.name, {})[f] = rb.matrix_world.translation.copy()

        fmin, fmax = min(frames), max(frames)
        deltas = []
        samples = []
        for name, framed in positions.items():
            if fmin in framed and fmax in framed:
                d = (framed[fmax] - framed[fmin]).length
                deltas.append(d)
                samples.append({'name': name, 'delta_m': round(d, 4)})
        if not deltas:
            results[group] = {'n_rigids': len(rbs), 'tip_delta_max_m': 0.0,
                              'tip_delta_mean_m': 0.0, 'samples': []}
            continue
        results[group] = {
            'n_rigids': len(rbs),
            'tip_delta_max_m': round(max(deltas), 4),
            'tip_delta_mean_m': round(sum(deltas) / len(deltas), 4),
            'samples': sorted(samples, key=lambda x: -x['delta_m'])[:6],
        }
    # Reset frame
    try:
        bpy.context.scene.frame_set(frames[0])
    except Exception:
        pass
    return results
