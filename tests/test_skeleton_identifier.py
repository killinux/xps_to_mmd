"""Offline tests for skeleton_identifier — mock bone tree, no Blender needed."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class FakeVector:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __sub__(self, other):
        return FakeVector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __add__(self, other):
        return FakeVector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __truediv__(self, s):
        return FakeVector(self.x / s, self.y / s, self.z / s)

    def __iadd__(self, other):
        self.x += other.x
        self.y += other.y
        self.z += other.z
        return self

    def __getitem__(self, i):
        return [self.x, self.y, self.z][i]

    @property
    def length(self):
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5

    def normalized(self):
        ln = self.length
        if ln < 1e-9:
            return FakeVector(0, 0, 0)
        return FakeVector(self.x / ln, self.y / ln, self.z / ln)


class FakeBone:
    def __init__(self, name, head, tail=None, parent=None):
        self.name = name
        self.head_local = FakeVector(*head)
        self.tail_local = FakeVector(*(tail or (head[0], head[1], head[2] + 0.1)))
        self.parent = parent
        self.children = []
        if parent:
            parent.children.append(self)


class FakeArmatureData:
    def __init__(self, bone_list):
        self.bones = bone_list


# Inject fake mathutils before importing skeleton_identifier
import types

mathutils = types.ModuleType("mathutils")
mathutils.Vector = lambda t: FakeVector(*t)
sys.modules["mathutils"] = mathutils

from skeleton_identifier import identify_skeleton, clear_cache


def build_xna_lara_inase():
    """Build a simplified Inase-like bone tree (XPS original, pre-rename)."""
    root = FakeBone("root ground", (0, 0, 0))
    hips = FakeBone("root hips", (0, 0, 0.72), parent=root)
    spine_lo = FakeBone("spine lower", (0, 0, 1.05), parent=hips)
    spine_mid = FakeBone("spine middle", (0, 0, 1.11), parent=spine_lo)
    spine_up = FakeBone("spine upper", (0, 0, 1.28), parent=spine_mid)
    neck = FakeBone("head neck lower", (0, 0.03, 1.41), parent=spine_up)
    head = FakeBone("head neck upper", (0, 0.01, 1.49), parent=neck)
    eye_l = FakeBone("head eyeball left", (0.028, -0.05, 1.55), parent=head)
    eye_r = FakeBone("head eyeball right", (-0.028, -0.05, 1.55), parent=head)

    # Left arm
    shoulder_l = FakeBone("arm left shoulder 1", (0.03, 0.04, 1.36), parent=spine_up)
    upper_arm_l = FakeBone("arm left shoulder 2", (0.13, 0.04, 1.36), parent=shoulder_l)
    elbow_l = FakeBone("arm left elbow", (0.30, 0.05, 1.23), parent=upper_arm_l)
    wrist_l = FakeBone("arm left wrist", (0.47, 0.05, 1.10), parent=elbow_l)
    # Fingers (3 bones each, 5 fingers)
    for fi, fname in enumerate(["1a", "2a", "3a", "4a", "5a"], 1):
        f1 = FakeBone(f"arm left finger {fname}", (0.48 + fi * 0.01, 0.04, 1.08), parent=wrist_l)
        f2 = FakeBone(f"arm left finger {fname[0]}b", (0.50 + fi * 0.01, 0.04, 1.06), parent=f1)
        FakeBone(f"arm left finger {fname[0]}c", (0.52 + fi * 0.01, 0.04, 1.04), parent=f2)

    # Right arm
    shoulder_r = FakeBone("arm right shoulder 1", (-0.03, 0.04, 1.36), parent=spine_up)
    upper_arm_r = FakeBone("arm right shoulder 2", (-0.13, 0.04, 1.36), parent=shoulder_r)
    elbow_r = FakeBone("arm right elbow", (-0.30, 0.05, 1.23), parent=upper_arm_r)
    wrist_r = FakeBone("arm right wrist", (-0.47, 0.05, 1.10), parent=elbow_r)
    for fi, fname in enumerate(["1a", "2a", "3a", "4a", "5a"], 1):
        f1 = FakeBone(f"arm right finger {fname}", (-0.48 - fi * 0.01, 0.04, 1.08), parent=wrist_r)
        f2 = FakeBone(f"arm right finger {fname[0]}b", (-0.50 - fi * 0.01, 0.04, 1.06), parent=f1)
        FakeBone(f"arm right finger {fname[0]}c", (-0.52 - fi * 0.01, 0.04, 1.04), parent=f2)

    # Left leg
    thigh_l = FakeBone("leg left thigh", (0.086, 0, 0.96), parent=hips)
    knee_l = FakeBone("leg left knee", (0.086, 0.01, 0.55), parent=thigh_l)
    ankle_l = FakeBone("leg left ankle", (0.086, 0.05, 0.15), parent=knee_l)
    FakeBone("leg left toes", (0.086, 0.02, 0.05), parent=ankle_l)

    # Right leg
    thigh_r = FakeBone("leg right thigh", (-0.086, 0, 0.96), parent=hips)
    knee_r = FakeBone("leg right knee", (-0.086, 0.01, 0.55), parent=thigh_r)
    ankle_r = FakeBone("leg right ankle", (-0.086, 0.05, 0.15), parent=knee_r)
    FakeBone("leg right toes", (-0.086, 0.02, 0.05), parent=ankle_r)

    # Collect all bones
    all_bones = []

    def collect(bone):
        all_bones.append(bone)
        for c in bone.children:
            collect(c)

    collect(root)
    return FakeArmatureData(all_bones)


def build_daz_genesis8():
    """Build a simplified DAZ Genesis 8 bone tree."""
    hip = FakeBone("hip", (0, 0, 1.0))
    abdomen_lo = FakeBone("abdomenLower", (0, 0, 1.05), parent=hip)
    abdomen_up = FakeBone("abdomenUpper", (0, 0, 1.15), parent=abdomen_lo)
    chest_lo = FakeBone("chestLower", (0, 0, 1.25), parent=abdomen_up)
    chest_up = FakeBone("chestUpper", (0, 0, 1.35), parent=chest_lo)
    neck = FakeBone("neckLower", (0, 0, 1.42), parent=chest_up)
    head = FakeBone("head", (0, 0, 1.50), parent=neck)
    eye_l = FakeBone("leftEye", (0.03, -0.05, 1.55), parent=head)
    eye_r = FakeBone("rightEye", (-0.03, -0.05, 1.55), parent=head)

    collar_l = FakeBone("lCollar", (0.04, 0, 1.38), parent=chest_up)
    shldr_l = FakeBone("lShldrBend", (0.15, 0, 1.38), parent=collar_l)
    farm_l = FakeBone("lForearmBend", (0.35, 0, 1.20), parent=shldr_l)
    hand_l = FakeBone("lHand", (0.50, 0, 1.10), parent=farm_l)
    for fi, fn in enumerate(["Thumb", "Index", "Mid", "Ring", "Pinky"]):
        f1 = FakeBone(f"l{fn}1", (0.52 + fi * 0.01, 0, 1.08), parent=hand_l)
        f2 = FakeBone(f"l{fn}2", (0.54 + fi * 0.01, 0, 1.06), parent=f1)
        FakeBone(f"l{fn}3", (0.56 + fi * 0.01, 0, 1.04), parent=f2)

    collar_r = FakeBone("rCollar", (-0.04, 0, 1.38), parent=chest_up)
    shldr_r = FakeBone("rShldrBend", (-0.15, 0, 1.38), parent=collar_r)
    farm_r = FakeBone("rForearmBend", (-0.35, 0, 1.20), parent=shldr_r)
    hand_r = FakeBone("rHand", (-0.50, 0, 1.10), parent=farm_r)
    for fi, fn in enumerate(["Thumb", "Index", "Mid", "Ring", "Pinky"]):
        f1 = FakeBone(f"r{fn}1", (-0.52 - fi * 0.01, 0, 1.08), parent=hand_r)
        f2 = FakeBone(f"r{fn}2", (-0.54 - fi * 0.01, 0, 1.06), parent=f1)
        FakeBone(f"r{fn}3", (-0.56 - fi * 0.01, 0, 1.04), parent=f2)

    thigh_l = FakeBone("lThighBend", (0.09, 0, 0.95), parent=hip)
    shin_l = FakeBone("lShin", (0.09, 0, 0.50), parent=thigh_l)
    foot_l = FakeBone("lMetatarsals", (0.09, -0.05, 0.08), parent=shin_l)

    thigh_r = FakeBone("rThighBend", (-0.09, 0, 0.95), parent=hip)
    shin_r = FakeBone("rShin", (-0.09, 0, 0.50), parent=thigh_r)
    foot_r = FakeBone("rMetatarsals", (-0.09, -0.05, 0.08), parent=shin_r)

    all_bones = []

    def collect(bone):
        all_bones.append(bone)
        for c in bone.children:
            collect(c)

    collect(hip)
    return FakeArmatureData(all_bones)


def test_inase():
    print("=== XNA Lara Inase ===")
    clear_cache()
    data = build_xna_lara_inase()
    r = identify_skeleton(data)

    expected = {
        "all_parents_bone": "root ground",
        "center_bone": "root hips",
        "upper_body_bone": "spine lower",
        "upper_body2_bone": "spine upper",
        "neck_bone": "head neck lower",
        "head_bone": "head neck upper",
        "left_shoulder_bone": "arm left shoulder 1",
        "right_shoulder_bone": "arm right shoulder 1",
        "left_upper_arm_bone": "arm left shoulder 2",
        "right_upper_arm_bone": "arm right shoulder 2",
        "left_lower_arm_bone": "arm left elbow",
        "right_lower_arm_bone": "arm right elbow",
        "left_hand_bone": "arm left wrist",
        "right_hand_bone": "arm right wrist",
        "left_thigh_bone": "leg left thigh",
        "right_thigh_bone": "leg right thigh",
        "left_calf_bone": "leg left knee",
        "right_calf_bone": "leg right knee",
        "left_foot_bone": "leg left ankle",
        "right_foot_bone": "leg right ankle",
        "left_toe_bone": "leg left toes",
        "right_toe_bone": "leg right toes",
        "left_eye_bone": "head eyeball left",
        "right_eye_bone": "head eyeball right",
    }

    ok = 0
    fail = 0
    for k, exp in sorted(expected.items()):
        got = r.get(k, "")
        if got == exp:
            ok += 1
        else:
            print(f"  FAIL {k}: expected '{exp}', got '{got}'")
            fail += 1

    # Also show any unexpected fills
    for k, v in sorted(r.items()):
        if v and k not in expected:
            print(f"  EXTRA {k} = {v}")

    total_filled = sum(1 for v in r.values() if v)
    print(f"  {ok}/{ok + fail} expected OK, {total_filled} total filled")
    return fail == 0


def test_daz():
    print("=== DAZ Genesis 8 ===")
    clear_cache()
    data = build_daz_genesis8()
    r = identify_skeleton(data)

    expected = {
        "center_bone": "hip",
        "neck_bone": "neckLower",
        "head_bone": "head",
        "left_shoulder_bone": "lCollar",
        "left_upper_arm_bone": "lShldrBend",
        "left_lower_arm_bone": "lForearmBend",
        "left_hand_bone": "lHand",
        "right_shoulder_bone": "rCollar",
        "right_upper_arm_bone": "rShldrBend",
        "right_lower_arm_bone": "rForearmBend",
        "right_hand_bone": "rHand",
        "left_thigh_bone": "lThighBend",
        "left_calf_bone": "lShin",
        "left_foot_bone": "lMetatarsals",
        "right_thigh_bone": "rThighBend",
        "right_calf_bone": "rShin",
        "right_foot_bone": "rMetatarsals",
        "left_eye_bone": "leftEye",
        "right_eye_bone": "rightEye",
    }

    ok = 0
    fail = 0
    for k, exp in sorted(expected.items()):
        got = r.get(k, "")
        if got == exp:
            ok += 1
        else:
            print(f"  FAIL {k}: expected '{exp}', got '{got}'")
            fail += 1

    for k, v in sorted(r.items()):
        if v and k not in expected:
            print(f"  EXTRA {k} = {v}")

    total_filled = sum(1 for v in r.values() if v)
    print(f"  {ok}/{ok + fail} expected OK, {total_filled} total filled")
    return fail == 0


def build_bip001():
    """Build a simplified Bip001 (3ds Max biped) bone tree."""
    root = FakeBone("Bip001 Root", (0, 0, 0))
    pelvis = FakeBone("Bip001 Pelvis", (0, 0, 0.95), parent=root)
    spine1 = FakeBone("Bip001 Spine1", (0, 0, 1.05), parent=pelvis)
    spine2 = FakeBone("Bip001 Spine2", (0, 0, 1.25), parent=spine1)
    neck = FakeBone("Bip001 Neck", (0, 0, 1.40), parent=spine2)
    head = FakeBone("Bip001 Head", (0, 0, 1.50), parent=neck)
    eye_l = FakeBone("Bip001 L Eye", (0.03, -0.05, 1.55), parent=head)
    eye_r = FakeBone("Bip001 R Eye", (-0.03, -0.05, 1.55), parent=head)

    clav_l = FakeBone("Bip001 L Clavicle", (0.04, 0, 1.35), parent=spine2)
    uarm_l = FakeBone("Bip001 L UpperArm", (0.15, 0, 1.35), parent=clav_l)
    farm_l = FakeBone("Bip001 L Forearm", (0.35, 0, 1.18), parent=uarm_l)
    hand_l = FakeBone("Bip001 L Hand", (0.50, 0, 1.08), parent=farm_l)
    for fi in range(5):
        f1 = FakeBone(f"Bip001 L Finger{fi}", (0.52 + fi * 0.01, 0, 1.06), parent=hand_l)
        f2 = FakeBone(f"Bip001 L Finger{fi}1", (0.54 + fi * 0.01, 0, 1.04), parent=f1)
        FakeBone(f"Bip001 L Finger{fi}2", (0.56 + fi * 0.01, 0, 1.02), parent=f2)

    clav_r = FakeBone("Bip001 R Clavicle", (-0.04, 0, 1.35), parent=spine2)
    uarm_r = FakeBone("Bip001 R UpperArm", (-0.15, 0, 1.35), parent=clav_r)
    farm_r = FakeBone("Bip001 R Forearm", (-0.35, 0, 1.18), parent=uarm_r)
    hand_r = FakeBone("Bip001 R Hand", (-0.50, 0, 1.08), parent=farm_r)
    for fi in range(5):
        f1 = FakeBone(f"Bip001 R Finger{fi}", (-0.52 - fi * 0.01, 0, 1.06), parent=hand_r)
        f2 = FakeBone(f"Bip001 R Finger{fi}1", (-0.54 - fi * 0.01, 0, 1.04), parent=f1)
        FakeBone(f"Bip001 R Finger{fi}2", (-0.56 - fi * 0.01, 0, 1.02), parent=f2)

    thigh_l = FakeBone("Bip001 L Thigh", (0.09, 0, 0.90), parent=pelvis)
    calf_l = FakeBone("Bip001 L Calf", (0.09, 0, 0.48), parent=thigh_l)
    foot_l = FakeBone("Bip001 L Foot", (0.09, -0.05, 0.08), parent=calf_l)

    thigh_r = FakeBone("Bip001 R Thigh", (-0.09, 0, 0.90), parent=pelvis)
    calf_r = FakeBone("Bip001 R Calf", (-0.09, 0, 0.48), parent=thigh_r)
    foot_r = FakeBone("Bip001 R Foot", (-0.09, -0.05, 0.08), parent=calf_r)

    all_bones = []

    def collect(bone):
        all_bones.append(bone)
        for c in bone.children:
            collect(c)

    collect(root)
    return FakeArmatureData(all_bones)


def test_bip001():
    print("=== Bip001 (3ds Max) ===")
    clear_cache()
    data = build_bip001()
    r = identify_skeleton(data)

    expected = {
        "all_parents_bone": "Bip001 Root",
        "center_bone": "Bip001 Pelvis",
        "neck_bone": "Bip001 Neck",
        "head_bone": "Bip001 Head",
        "left_shoulder_bone": "Bip001 L Clavicle",
        "right_shoulder_bone": "Bip001 R Clavicle",
        "left_upper_arm_bone": "Bip001 L UpperArm",
        "right_upper_arm_bone": "Bip001 R UpperArm",
        "left_lower_arm_bone": "Bip001 L Forearm",
        "right_lower_arm_bone": "Bip001 R Forearm",
        "left_hand_bone": "Bip001 L Hand",
        "right_hand_bone": "Bip001 R Hand",
        "left_thigh_bone": "Bip001 L Thigh",
        "left_calf_bone": "Bip001 L Calf",
        "left_foot_bone": "Bip001 L Foot",
        "right_thigh_bone": "Bip001 R Thigh",
        "right_calf_bone": "Bip001 R Calf",
        "right_foot_bone": "Bip001 R Foot",
        "left_eye_bone": "Bip001 L Eye",
        "right_eye_bone": "Bip001 R Eye",
    }

    ok = 0
    fail = 0
    for k, exp in sorted(expected.items()):
        got = r.get(k, "")
        if got == exp:
            ok += 1
        else:
            print(f"  FAIL {k}: expected '{exp}', got '{got}'")
            fail += 1

    for k, v in sorted(r.items()):
        if v and k not in expected:
            print(f"  EXTRA {k} = {v}")

    total_filled = sum(1 for v in r.values() if v)
    print(f"  {ok}/{ok + fail} expected OK, {total_filled} total filled")
    return fail == 0


if __name__ == "__main__":
    passed = 0
    total = 0

    for test_fn in [test_inase, test_daz, test_bip001]:
        total += 1
        if test_fn():
            passed += 1

    print(f"\n{'PASS' if passed == total else 'FAIL'}: {passed}/{total}")
