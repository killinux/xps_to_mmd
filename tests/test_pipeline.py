"""XPS→PMX pipeline end-to-end test.

Entry: `python cli/cli.py exec --file tests/test_pipeline.py` from AWS.
Or directly inside Blender: `exec(open('.../test_pipeline.py').read())`.

Environment overrides (via Blender's bpy.app.driver_namespace):
  ITER_N      — iteration number (default 1)
  MODEL       — 'inase' or 'reika' (default 'inase')
  TEST_PHASE  — 'A' / 'AB' / 'ABC' / 'ABCD' / 'ABCDE' / 'all' (default 'all')
  SKIP_VMD    — truthy to skip Phase E
"""
import bpy
import sys
import os
import json
import traceback
from pathlib import Path

# Make sure we can import helpers via full addons path
_here = Path('/Users/bytedance/Library/Application Support/Blender/3.6/scripts/addons/xps_to_mmd')
sys.path.insert(0, str(_here))

# Lazy imports after path is set
from tests.helpers import common, phase_a, phase_b, phase_c, phase_d, phase_e

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
MODELS = {
    'inase': {
        'xps': '/Users/bytedance/Downloads/demo/inase (purifier)_lezisell-A/xps-b.xps',
        'target_pmx': '/Users/bytedance/Downloads/demo/Purifier Inase 18/Purifier Inase 18 None.pmx',
        'preset': '3ds_max',
    },
    'reika': {
        'xps': '/Users/bytedance/Downloads/demo/Reika/xps.xps',
        'target_pmx': '/Users/bytedance/Downloads/demo/Reika Shimohira 2 18/Reika Shimohira 2 18 None.pmx',
        'preset': 'daz_poser',
    },
}

VMD_PATH = '/Users/bytedance/Downloads/demo/永劫无间摇香2025.2.21by小王动画/永劫无间摇香2025.2.21.vmd'


# Read config (Blender has no os.environ for scripts executed via remote exec)
ITER_N = int(os.environ.get('ITER_N', '1'))
MODEL = os.environ.get('MODEL', 'inase')
TEST_PHASE = os.environ.get('TEST_PHASE', 'all')  # A/AB/ABC/ABCD/ABCDE/all
SKIP_VMD = os.environ.get('SKIP_VMD', '').lower() in ('1', 'true', 'yes')

cfg = MODELS[MODEL]


def _report():
    out_dir = common.ensure_out_dir(ITER_N)
    print(f"[test_pipeline] iter={ITER_N} model={MODEL} phase={TEST_PHASE}")
    print(f"[test_pipeline] out_dir={out_dir}")

    report = {
        'iter': ITER_N,
        'model': MODEL,
        'config': cfg,
        'phase': TEST_PHASE,
    }

    # Hard reset
    try:
        common.clean_scene()
    except Exception as e:
        print(f"clean_scene fail: {e}")

    # Phase A — smoke
    try:
        a = phase_a.run_main_pipeline(cfg['xps'], cfg['preset'], report)
        report['phase_A'] = a
        fails = [k for k, v in a.items() if isinstance(v, dict) and v.get('status') == 'fail']
        report['phase_A_fails'] = fails
        print(f"[phase A] done. fails={fails}")
    except Exception as e:
        traceback.print_exc()
        report['phase_A_exception'] = str(e)
        print(f"[phase A] exception: {e}")

    if TEST_PHASE == 'A':
        _write_report(out_dir, report)
        return

    # Phase B — round-trip
    try:
        arm = common.find_armature()
        if arm is None:
            raise RuntimeError("no armature before PMX export")
        out_pmx = str(out_dir / f'output_{MODEL}.pmx')
        phase_b.export_pmx(out_pmx, arm)
        report['phase_B_export'] = {'status': 'ok', 'file': out_pmx,
                                    'size': os.path.getsize(out_pmx) if os.path.exists(out_pmx) else 0}
        # Reimport
        b = phase_b.reimport_and_check(out_pmx, None, None, None)
        report['phase_B_reimport'] = b
        print(f"[phase B] export ok, reimport n_bones={b.get('n_bones')}")
    except Exception as e:
        traceback.print_exc()
        report['phase_B_exception'] = str(e)

    if TEST_PHASE in ('AB',):
        _write_report(out_dir, report)
        return

    # Phase C — physics bake + tip delta
    # Note: After Phase B we're in a fresh reimported scene, which is fine for physics bake
    try:
        c = phase_c.bake_and_measure(frames=(1, 120))
        report['phase_C'] = c
        print(f"[phase C] hair={c.get('hair', {}).get('tip_delta_max_m')} breast={c.get('breast', {}).get('tip_delta_max_m')}")
    except Exception as e:
        traceback.print_exc()
        report['phase_C_exception'] = str(e)

    if TEST_PHASE in ('ABC',):
        _write_report(out_dir, report)
        return

    # Phase D — structural diff vs target
    try:
        from tests.helpers.common import CORE_MMD_BONES
        out_pmx = str(out_dir / f'output_{MODEL}.pmx')
        d = phase_d.compare_vs_target(out_pmx, cfg['target_pmx'], CORE_MMD_BONES)
        report['phase_D'] = d
        print(f"[phase D] symmetric_diff={d.get('n_symmetric_diff')} "
              f"rbs={d.get('rb_counts')} joints={d.get('joint_counts')}")
    except Exception as e:
        traceback.print_exc()
        report['phase_D_exception'] = str(e)

    if TEST_PHASE in ('ABCD',) or SKIP_VMD:
        _write_report(out_dir, report)
        return

    # Phase E — VMD playback
    try:
        out_pmx = str(out_dir / f'output_{MODEL}.pmx')
        e = phase_e.vmd_drift(out_pmx, cfg['target_pmx'], VMD_PATH,
                              frames=(0, 30, 60, 120, 180))
        report['phase_E'] = e
        print(f"[phase E] max_wrist_drift_ratio={e.get('max_wrist_drift_ratio')} pass={e.get('pass_gate')}")
    except Exception as ex:
        traceback.print_exc()
        report['phase_E_exception'] = str(ex)

    _write_report(out_dir, report)
    return report


def _write_report(out_dir, report):
    common.jwrite(out_dir / 'report.json', report)
    # Human-readable summary
    lines = [
        f"# XPS→PMX pipeline iter {ITER_N} ({MODEL})",
        "",
        f"**Phase**: {TEST_PHASE}",
        f"**Model**: {report['model']}",
        f"**XPS**: `{cfg['xps']}`",
        f"**Preset**: `{cfg['preset']}`",
        "",
        "## Phase A (smoke)",
    ]
    a = report.get('phase_A', {})
    for step, res in a.items():
        if isinstance(res, dict):
            status = res.get('status', '?')
            lines.append(f"- **{step}**: `{status}`")
            if status == 'fail':
                lines.append(f"    - error: `{res.get('error', '')}`")
    lines.append("")
    if 'phase_B_reimport' in report:
        b = report['phase_B_reimport']
        lines.extend([
            "## Phase B (round-trip)",
            f"- n_bones: {b.get('n_bones')}",
            f"- n_rigid_total: {b.get('n_rigid_total')}",
            f"- n_joint_total: {b.get('n_joint_total')}",
            f"- n_dangling_joints: {b.get('n_dangling_joints')}",
            f"- missing_core_bones: {b.get('missing_core_bones')}",
            f"- has_上半身3: {b.get('has_上半身3')}",
            "",
        ])
    if 'phase_C' in report:
        c = report['phase_C']
        lines.append("## Phase C (physics bake)")
        for k, v in c.items():
            if isinstance(v, dict):
                lines.append(f"- **{k}** n={v.get('n_rigids')} tip_delta max={v.get('tip_delta_max_m')}m mean={v.get('tip_delta_mean_m')}m")
        lines.append("")
    if 'phase_D' in report:
        d = report['phase_D']
        lines.extend([
            "## Phase D (target diff)",
            f"- our_n_bones: {d.get('our_n_bones')}",
            f"- target_n_bones: {d.get('target_n_bones')}",
            f"- n_symmetric_diff: {d.get('n_symmetric_diff')}",
            f"- rb_counts: {d.get('rb_counts')}",
            f"- joint_counts: {d.get('joint_counts')}",
            f"- worst bone dir deltas: {d.get('core_bone_dir_delta_deg', [])[:5]}",
            f"- top VG diffs: {d.get('vg_count_top_diffs', [])[:5]}",
            "",
        ])
    if 'phase_E' in report:
        e = report['phase_E']
        lines.extend([
            "## Phase E (VMD playback)",
            f"- our_armature_h_m: {e.get('our_armature_h_m')}",
            f"- target_armature_h_m: {e.get('target_armature_h_m')}",
            f"- max_wrist_drift_ratio: {e.get('max_wrist_drift_ratio')}  (ship gate < 0.05)",
            f"- pass_gate: **{e.get('pass_gate')}**",
            f"- worst samples: {e.get('samples_worst', [])[:5]}",
            "",
        ])

    common.mdwrite(out_dir / 'report.md', "\n".join(lines))
    print(f"[test_pipeline] report written to {out_dir / 'report.md'}")


# Always execute when invoked (whether via cli exec or direct)
_report()
