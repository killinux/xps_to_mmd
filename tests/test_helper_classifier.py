"""Offline tests for helper_classifier — uses same mock bones as skeleton test."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_skeleton_identifier import (
    FakeVector, FakeBone, FakeArmatureData,
    build_xna_lara_inase,
)

import types
mathutils = types.ModuleType("mathutils")
mathutils.Vector = lambda t: FakeVector(*t)
sys.modules["mathutils"] = mathutils

from skeleton_identifier import identify_skeleton, clear_cache
from helper_classifier import classify_helpers


def build_inase_with_helpers():
    """XNA Lara Inase with XPS helper bones (xtra, foretwist, boob, etc.)."""
    data = build_xna_lara_inase()
    bones = {b.name: b for b in data.bones}

    hips = bones["root hips"]
    spine_up = bones["spine upper"]
    upper_arm_l = bones["arm left shoulder 2"]
    elbow_l = bones["arm left elbow"]
    upper_arm_r = bones["arm right shoulder 2"]
    elbow_r = bones["arm right elbow"]
    thigh_l = bones["leg left thigh"]
    thigh_r = bones["leg right thigh"]

    # Pelvis: child of hips, centered
    pelvis = FakeBone("unused bip001 pelvis", (0, 0, 1.02), parent=hips)

    # Hip helpers: children of pelvis, off-center
    FakeBone("unused bip001 xtra08", (0.06, 0, 1.01), parent=pelvis)
    FakeBone("unused bip001 xtra08opp", (-0.06, 0, 1.01), parent=pelvis)

    # Thigh helpers: children of thigh
    FakeBone("unused bip001 xtra04", (0.085, 0, 1.02), parent=thigh_l)
    FakeBone("unused bip001 xtra02", (-0.085, 0, 1.02), parent=thigh_r)

    # Upper arm twist candidates (on arm segment)
    FakeBone("bip001 xtra07", (0.20, 0.04, 1.30), parent=upper_arm_l)
    FakeBone("bip001 xtra07pp", (0.23, 0.05, 1.28), parent=upper_arm_l)
    FakeBone("bip001 xtra07 r", (-0.20, 0.04, 1.30), parent=upper_arm_r)

    # Forearm twist candidates
    FakeBone("bip001 foretwist", (0.40, 0.05, 1.15), parent=elbow_l)
    FakeBone("bip001 muscle_elbow_left", (0.35, 0.05, 1.19), parent=elbow_l)

    # Breast helpers: children of spine upper
    FakeBone("boob left 1", (0.045, -0.03, 1.36), parent=spine_up)
    FakeBone("boob right 1", (-0.045, -0.03, 1.36), parent=spine_up)

    # Dummy/shadow bones
    FakeBone("_dummy_test", (0, 0, 0), parent=hips)
    FakeBone("_shadow_test", (0, 0, 0), parent=hips)

    all_bones = []

    def collect(bone):
        all_bones.append(bone)
        for c in bone.children:
            collect(c)

    for b in data.bones:
        if b.parent is None:
            collect(b)

    return FakeArmatureData(all_bones)


def test_inase_helpers():
    print("=== Helper Classification (Inase) ===")
    data = build_inase_with_helpers()

    clear_cache()
    smap = identify_skeleton(data)

    classification = classify_helpers(data, smap)

    expected = {
        "unused bip001 pelvis": "pelvis",
        "unused bip001 xtra08": "preserve",
        "unused bip001 xtra08opp": "preserve",
        "unused bip001 xtra04": "preserve",
        "unused bip001 xtra02": "preserve",
        "bip001 xtra07": "twist",
        "bip001 xtra07pp": "twist",
        "bip001 xtra07 r": "twist",
        "bip001 foretwist": "twist",
        "bip001 muscle_elbow_left": "twist",
        "boob left 1": "preserve",
        "boob right 1": "preserve",
        "_dummy_test": "ignore",
        "_shadow_test": "ignore",
        "root ground": "mapped",
        "root hips": "mapped",
        "spine middle": "mapped",
        "arm left shoulder 1": "mapped",
        "head neck upper": "mapped",
    }

    ok = fail = 0
    for k, exp in sorted(expected.items()):
        got = classification.get(k, "???")
        if got == exp:
            ok += 1
        else:
            print(f"  FAIL {k}: got={got} exp={exp}")
            fail += 1

    print(f"  {ok}/{ok + fail} correct")
    return fail == 0


if __name__ == "__main__":
    passed = 0
    total = 0
    for fn in [test_inase_helpers]:
        total += 1
        if fn():
            passed += 1
    print(f"\n{'PASS' if passed == total else 'FAIL'}: {passed}/{total}")
