from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import trimesh


GLB_PATH = r"F:\home\exploded-hexagon-home\out\massing_s23_d7.glb"
FT_TO_M = 0.3048
CENTER_PLAN = np.array([0.0, 0.0], dtype=float)
Z_MIN_FT, Z_MAX_FT = -2.0, 2.0
EDGE_TOL_FT = 1.0

# Flat-top hex (s=23), CCW
V = {
    "v0": np.array([23.0, 0.0]),
    "v1": np.array([11.5, 19.92]),
    "v2": np.array([-11.5, 19.92]),
    "v3": np.array([-23.0, 0.0]),
    "v4": np.array([-11.5, -19.92]),
    "v5": np.array([11.5, -19.92]),
}

WING_EDGES_PLAN = {
    "wing_a": (V["v5"], V["v0"]),  # atrium edge
    "wing_b": (V["v3"], V["v4"]),  # atrium edge
}


def point_segment_distance_2d(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> tuple[float, np.ndarray]:
    ab = b - a
    ab2 = float(np.dot(ab, ab))
    if ab2 <= 1e-12:
        return float(np.linalg.norm(p - a)), a
    t = float(np.dot(p - a, ab) / ab2)
    t = max(0.0, min(1.0, t))
    q = a + t * ab
    return float(np.linalg.norm(p - q)), q


def world_tris_for_geometry(scene: trimesh.Scene, geom_name: str) -> list[np.ndarray]:
    geom = scene.geometry[geom_name]
    tris = []
    for node_name in scene.graph.nodes_geometry:
        if scene.graph[node_name][1] != geom_name:
            continue
        mat, _ = scene.graph.get(node_name)
        verts_h = np.hstack([geom.vertices, np.ones((len(geom.vertices), 1))])
        verts_w = (mat @ verts_h.T).T[:, :3]
        faces = geom.faces
        tris.append(verts_w[faces])
    return tris


def to_glb_plan_2d(pxy_ft: np.ndarray) -> np.ndarray:
    # Export applies rotate_x(-90): (x,y,z)->(x,z,-y), then feet->meters.
    # So horizontal plan for GLB is (x_glb, z_glb) = (x_ft, -y_ft) * 0.3048.
    return np.array([pxy_ft[0] * FT_TO_M, -pxy_ft[1] * FT_TO_M], dtype=float)


def analyze_edge(scene: trimesh.Scene, wing_key: str) -> None:
    edge_a = to_glb_plan_2d(WING_EDGES_PLAN[wing_key][0])
    edge_b = to_glb_plan_2d(WING_EDGES_PLAN[wing_key][1])
    edge_mid = 0.5 * (edge_a + edge_b)
    atrium_dir = to_glb_plan_2d(CENTER_PLAN) - edge_mid
    atrium_dir /= np.linalg.norm(atrium_dir)

    candidate_geoms = [g for g in scene.geometry.keys() if g.lower().startswith(wing_key + "_")]
    print(f"\n[{wing_key}] matching geometries: {len(candidate_geoms)}")
    for g in sorted(candidate_geoms):
        print(f"  - {g}")

    z_by_geom: dict[str, list[tuple[float, float]]] = defaultdict(list)
    signed_offsets_by_geom: dict[str, list[float]] = defaultdict(list)
    wrong_normals = []
    atrium_face_normals_checked = 0
    count_near = 0

    for geom_name in candidate_geoms:
        all_tris_groups = world_tris_for_geometry(scene, geom_name)
        for tris in all_tris_groups:
            for tri in tris:
                tri_y_ft = tri[:, 1] / FT_TO_M
                if tri_y_ft.max() < Z_MIN_FT or tri_y_ft.min() > Z_MAX_FT:
                    continue
                c = tri.mean(axis=0)
                c_plan = np.array([c[0], c[2]])
                d, q = point_segment_distance_2d(c_plan, edge_a, edge_b)
                if d > EDGE_TOL_FT * FT_TO_M:
                    continue
                count_near += 1
                z_by_geom[geom_name].append((float(tri_y_ft.min()), float(tri_y_ft.max())))

                # Vertical-ish face only for normal test
                v1 = tri[1] - tri[0]
                v2 = tri[2] - tri[0]
                n = np.cross(v1, v2)
                n_norm = np.linalg.norm(n)
                if n_norm <= 1e-10:
                    continue
                n /= n_norm
                # Wall faces are mostly horizontal-normal in XZ (small Y component).
                if abs(float(n[1])) > 0.25:
                    continue

                # Atrium-facing side only: centroid sits between edge and center.
                to_centroid = c_plan - q
                signed_offsets_by_geom[geom_name].append(float(np.dot(to_centroid, atrium_dir) / FT_TO_M))
                if float(np.dot(to_centroid, atrium_dir)) < -1e-6:
                    continue

                # Expected: normal points toward center.
                n_plan = np.array([n[0], n[2]])
                atrium_face_normals_checked += 1
                if float(np.dot(n_plan, atrium_dir)) < -1e-4:
                    wrong_normals.append((geom_name, c.copy(), n.copy(), float(tri_y_ft.min()), float(tri_y_ft.max())))

    print(f"[{wing_key}] triangles near atrium edge (z_ft in [{Z_MIN_FT}, {Z_MAX_FT}]): {count_near}")
    if not z_by_geom:
        print(f"[{wing_key}] no matching triangles found.")
    else:
        print(f"[{wing_key}] z-ranges by geometry:")
        for g in sorted(z_by_geom):
            zs = np.array(z_by_geom[g], dtype=float)
            print(f"  {g}: overall z_ft [{zs[:,0].min():.4f}, {zs[:,1].max():.4f}] from {len(zs)} tris")
            if g in signed_offsets_by_geom and signed_offsets_by_geom[g]:
                so = np.array(signed_offsets_by_geom[g], dtype=float)
                print(f"    offset from atrium edge toward center (ft): [{so.min():.4f}, {so.max():.4f}]")

    print(f"[{wing_key}] atrium-facing vertical tris checked for normal direction: {atrium_face_normals_checked}")
    if wrong_normals:
        print(f"[{wing_key}] WRONG-WAY atrium-facing normals: {len(wrong_normals)}")
        for row in wrong_normals[:20]:
            g, c, n, z0, z1 = row
            print(f"  {g}: centroid=({c[0]:.3f},{c[1]:.3f},{c[2]:.3f}) normal=({n[0]:.3f},{n[1]:.3f},{n[2]:.3f}) z_ft=[{z0:.3f},{z1:.3f}]")
        if len(wrong_normals) > 20:
            print(f"  ... {len(wrong_normals)-20} more")
    else:
        print(f"[{wing_key}] no wrong-way atrium-facing normals found.")


def analyze_marble_overlap(scene: trimesh.Scene) -> None:
    # Quick z-fight heuristic: wall tris close to z=-1 and atrium floor top tris at z=-1
    marble_geoms = [g for g in scene.geometry if "atrium_floor" in g.lower()]
    wing_geoms = [g for g in scene.geometry if "wing_a_" in g.lower() or "wing_b_" in g.lower()]
    print(f"\n[overlap] atrium_floor geoms: {len(marble_geoms)}, wing_a/b geoms: {len(wing_geoms)}")

    marble_points = []
    for g in marble_geoms:
        for tris in world_tris_for_geometry(scene, g):
            for tri in tris:
                # atrium marble top is at z_ft=-1 -> y_glb=-0.3048m
                if np.all(np.abs(tri[:, 1] + FT_TO_M) < 2e-4):
                    marble_points.append(np.array([tri[:, 0].mean(), tri[:, 2].mean()]))
    marble_points = np.array(marble_points) if marble_points else np.zeros((0, 2))
    print(f"[overlap] marble top tris exactly at z=-1: {len(marble_points)}")

    close_wall = 0
    for g in wing_geoms:
        for tris in world_tris_for_geometry(scene, g):
            for tri in tris:
                ymin_ft, ymax_ft = float((tri[:, 1] / FT_TO_M).min()), float((tri[:, 1] / FT_TO_M).max())
                if not (ymin_ft <= -1.0 <= ymax_ft):
                    continue
                cxy = np.array([tri[:, 0].mean(), tri[:, 2].mean()])
                if marble_points.size:
                    d = np.linalg.norm(marble_points - cxy, axis=1).min()
                    if d < 0.05 * FT_TO_M:
                        close_wall += 1
    print(f"[overlap] wing wall tris crossing z=-1 and within 0.05ft of marble-top tri centroids: {close_wall}")


def main() -> None:
    scene = trimesh.load(GLB_PATH, force="scene")
    print(f"Loaded: {GLB_PATH}")
    print(f"Scene geoms: {len(scene.geometry)}")
    analyze_edge(scene, "wing_a")
    analyze_edge(scene, "wing_b")
    analyze_marble_overlap(scene)


if __name__ == "__main__":
    main()
