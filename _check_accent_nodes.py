import bpy

m = bpy.data.materials.get("AccentWall")
print("has_mat", bool(m))
if not m or not m.use_nodes:
    raise SystemExit(0)

has_dot = False
has_gt = False
has_mix = False
gt_threshold = None
for n in m.node_tree.nodes:
    if n.type == "VECT_MATH" and getattr(n, "operation", "") == "DOT_PRODUCT":
        has_dot = True
    if n.type == "MATH" and getattr(n, "operation", "") == "GREATER_THAN":
        has_gt = True
        gt_threshold = n.inputs[1].default_value
    if n.type == "MIX_SHADER":
        has_mix = True

print("dot", has_dot, "gt", has_gt, "mix", has_mix, "gt_threshold", gt_threshold)
