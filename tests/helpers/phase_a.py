"""Phase A — Pipeline smoke: trigger each operator, assert expected state."""
import bpy
import os

from .common import find_armature, set_active


def run_main_pipeline(xps_path, preset_name, report):
    """Run the full main pipeline from import through mmd_tools convert + physics.
    Returns dict of state checkpoints for each step."""
    results = {}

    # Step 0: Import XPS
    try:
        # ImportHelper operators use the filepath parameter
        bpy.ops.object.xps_import_xps(filepath=xps_path, auto_scale=True)
        arm = find_armature()
        assert arm is not None, "no armature after import"
        set_active(arm)
        results['0_import'] = {
            'status': 'ok',
            'armature': arm.name,
            'n_bones': len(arm.data.bones),
        }
    except Exception as e:
        results['0_import'] = {'status': 'fail', 'error': str(e)}
        return results  # no point continuing

    # Load preset
    try:
        bpy.ops.object.xps_load_preset(preset_name=preset_name)
        results['0_preset'] = {'status': 'ok', 'preset': preset_name}
    except Exception as e:
        results['0_preset'] = {'status': 'fail', 'error': str(e)}

    # Step 0.5: Correct bones (set origin at upper body, clear animation)
    try:
        bpy.ops.object.xps_correct_bones()
        results['0_5_correct'] = {'status': 'ok'}
    except Exception as e:
        results['0_5_correct'] = {'status': 'fail', 'error': str(e)}

    # Step 1: Rename to MMD
    try:
        bpy.ops.object.xps_rename_to_mmd()
        arm = bpy.context.active_object
        results['1_rename'] = {
            'status': 'ok',
            'has_上半身': '上半身' in arm.data.bones,
            'has_左腕': '左腕' in arm.data.bones,
            'has_左足': '左足' in arm.data.bones,
            'missing_core': [
                b for b in ('上半身', '上半身2', '左腕', '左足', '首', '頭')
                if b not in arm.data.bones
            ],
        }
    except Exception as e:
        results['1_rename'] = {'status': 'fail', 'error': str(e)}

    # Step 1.5: L1 rest pose alignment (canonical) — reduces wrist drift in VMD playback
    # Runs after rename so MMD-side bone names (腕.L/ひじ.L/手首.L or 左腕/左ひじ/左手首) exist
    try:
        bpy.ops.object.xps_fix_forearm_bend()
        results['1_5_fix_forearm'] = {'status': 'ok'}
    except Exception as e:
        results['1_5_fix_forearm'] = {'status': 'warn', 'error': str(e)}
    try:
        bpy.ops.object.xps_align_arms_to_canonical()
        results['1_6_align_arms'] = {'status': 'ok'}
    except Exception as e:
        results['1_6_align_arms'] = {'status': 'warn', 'error': str(e)}
    try:
        bpy.ops.object.xps_align_fingers_to_canonical()
        results['1_7_align_fingers'] = {'status': 'ok'}
    except Exception as e:
        results['1_7_align_fingers'] = {'status': 'warn', 'error': str(e)}

    # Step 2: Complete missing bones (上半身3 auto-created here)
    try:
        bpy.ops.object.xps_complete_missing_bones()
        arm = bpy.context.active_object
        c3 = arm.data.bones.get('上半身3')
        center = arm.data.bones.get('センター')
        results['2_complete'] = {
            'status': 'ok',
            '全ての親': '全ての親' in arm.data.bones,
            'センター': 'センター' in arm.data.bones,
            '上半身3': '上半身3' in arm.data.bones,
            '上半身3_parent': c3.parent.name if c3 and c3.parent else None,
            'センター_tail_below_head': (
                center.tail_local.z < center.head_local.z if center else None
            ),
        }
    except Exception as e:
        results['2_complete'] = {'status': 'fail', 'error': str(e)}

    # Step 3: Add IK
    try:
        bpy.ops.object.xps_add_mmd_ik()
        arm = bpy.context.active_object
        ik_bones_have_ik = 0
        for side_bone in ('左足ＩＫ', '右足ＩＫ', '左足IK', '右足IK'):
            pb = arm.pose.bones.get(side_bone)
            if pb:
                has_ik = any(c.type == 'IK' for c in pb.constraints)
                if has_ik:
                    ik_bones_have_ik += 1
        results['3_ik'] = {'status': 'ok', 'ik_bones_found': ik_bones_have_ik}
    except Exception as e:
        results['3_ik'] = {'status': 'fail', 'error': str(e)}

    # Step 4: Create bone group / collection
    try:
        bpy.ops.object.xps_create_bone_group()
        results['4_bone_group'] = {'status': 'ok'}
    except Exception as e:
        results['4_bone_group'] = {'status': 'fail', 'error': str(e)}

    # Step 5: Use mmd_tools convert
    try:
        bpy.ops.object.xps_use_mmd_tools_convert()
        from mmd_tools.core.model import Model
        arm = bpy.context.active_object
        # After convert, active might be the root or the armature — find armature
        if arm.type != 'ARMATURE':
            arm = find_armature()
            set_active(arm)
        root = Model.findRoot(arm)
        results['5_mmd_convert'] = {
            'status': 'ok' if root else 'fail',
            'root': root.name if root else None,
        }
    except Exception as e:
        results['5_mmd_convert'] = {'status': 'fail', 'error': str(e)}

    # Secondary bones (Tab 2 — optional but we run them for Inase)
    # D bones
    try:
        bpy.ops.object.xps_add_leg_d_bones()
        arm = find_armature()
        results['6_d_bones'] = {
            'status': 'ok',
            '左足D': '左足D' in arm.data.bones,
        }
    except Exception as e:
        results['6_d_bones'] = {'status': 'warn', 'error': str(e)}

    # Twist bones
    try:
        bpy.ops.object.xps_add_twist_bone()
        arm = find_armature()
        results['7_twist'] = {
            'status': 'ok',
            '左腕捩': '左腕捩' in arm.data.bones,
            '左腕捩1': '左腕捩1' in arm.data.bones,
        }
    except Exception as e:
        results['7_twist'] = {'status': 'warn', 'error': str(e)}

    # Shoulder P
    try:
        bpy.ops.object.xps_add_shoulder_p_bones()
        arm = find_armature()
        shoulder_p = arm.data.bones.get('左肩P')
        results['8_shoulder_p'] = {
            'status': 'ok',
            '左肩P': '左肩P' in arm.data.bones,
            '左肩P_parent': shoulder_p.parent.name if shoulder_p and shoulder_p.parent else None,
        }
    except Exception as e:
        results['8_shoulder_p'] = {'status': 'warn', 'error': str(e)}

    # Re-apply additional_transform (R1 / 坑 3 — 血泪教训)
    try:
        bpy.ops.mmd_tools.apply_additional_transform()
        results['8_5_apply_add_transform'] = {'status': 'ok'}
    except Exception as e:
        results['8_5_apply_add_transform'] = {'status': 'warn', 'error': str(e)}

    # Phase physics — body / hair / breast
    for op_name, key in [
        ('xps_generate_body_rigid_bodies', '9_body_rb'),
        ('xps_generate_hair_physics', '10_hair_rb'),
        ('xps_generate_breast_physics', '11_breast_rb'),
    ]:
        try:
            # Re-set armature active before each op (createRigidBody changes active)
            arm = find_armature()
            if arm is None:
                raise RuntimeError("no armature")
            set_active(arm)
            getattr(bpy.ops.object, op_name)()
            # Count rigid bodies created with matching prefix
            prefixes = {
                '9_body_rb': 'auto_rb_body_',
                '10_hair_rb': 'auto_rb_hair_',
                '11_breast_rb': 'auto_rb_breast_',
            }
            prefix = prefixes[key]
            rbs = [o for o in bpy.data.objects
                   if o.mmd_type == 'RIGID_BODY' and o.name.startswith(prefix)]
            joints = [o for o in bpy.data.objects
                      if o.mmd_type == 'JOINT' and o.name.startswith(f'J.{prefix}')]
            # Assert no bone name starts with _dummy_/_shadow_ (R2 / dummy-shadow check)
            bad = [o.name for o in rbs
                   if o.mmd_rigid.bone.startswith(('_dummy_', '_shadow_'))]
            results[key] = {
                'status': 'ok' if not bad else 'fail',
                'n_rigid': len(rbs),
                'n_joint': len(joints),
                'bad_bone_bindings': bad,
            }
        except Exception as e:
            results[key] = {'status': 'fail', 'error': str(e)}

    return results
