"""Phase B — PMX round-trip: export, import to fresh scene, verify structure."""
import bpy


def export_pmx(out_path, armature):
    """Call mmd_tools.export_pmx for the MMD model wrapping this armature."""
    from mmd_tools.core.model import Model
    root = Model.findRoot(armature)
    if root is None:
        raise RuntimeError("no MMD root found; run step 5 first")
    # Need to have root selected+active for mmd_tools export
    bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.mode != 'OBJECT' else None
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.mmd_tools.export_pmx(filepath=out_path, scale=12.5)
    return out_path


def reimport_and_check(pmx_path, expected_rb_body, expected_rb_hair, expected_rb_breast):
    """Fresh scene, import PMX, count rigid bodies / joints / bones / check dangling."""
    # Clean slate
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    try:
        bpy.ops.outliner.orphans_purge(do_recursive=True)
    except Exception:
        pass

    bpy.ops.mmd_tools.import_model(filepath=pmx_path, scale=0.08,
                                   types={'MESH', 'ARMATURE', 'PHYSICS', 'MORPHS'})

    # Count state post-reimport
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if not arm:
        return {'status': 'fail', 'error': 'no armature after reimport'}

    rbs = [o for o in bpy.data.objects if o.mmd_type == 'RIGID_BODY']
    joints = [o for o in bpy.data.objects if o.mmd_type == 'JOINT']

    # Check dangling joints
    rb_names = {o.name for o in rbs}
    dangling = []
    for j in joints:
        rbc = j.rigid_body_constraint
        a = rbc.object1.name if rbc and rbc.object1 else None
        b = rbc.object2.name if rbc and rbc.object2 else None
        if a is None or b is None or a not in rb_names or b not in rb_names:
            dangling.append({'joint': j.name, 'rigid_a': a, 'rigid_b': b})

    # MMD core bones present
    from .common import CORE_MMD_BONES
    missing_core = [b for b in CORE_MMD_BONES if b not in arm.data.bones]

    return {
        'status': 'ok' if not dangling and not missing_core else 'fail',
        'n_bones': len(arm.data.bones),
        'n_rigid_total': len(rbs),
        'n_joint_total': len(joints),
        'n_dangling_joints': len(dangling),
        'dangling_samples': dangling[:5],
        'missing_core_bones': missing_core,
        'has_上半身3': '上半身3' in arm.data.bones,
    }
