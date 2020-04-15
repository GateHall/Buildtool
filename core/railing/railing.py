import math
import bmesh
from bmesh.types import BMFace, BMEdge
from mathutils import Vector, Euler, Quaternion
from ...utils import (
    FaceMap,
    map_new_faces,
    add_facemap_for_groups,
    filter_vertical_edges,
    filter_geom,
    edge_vector,
    sort_edges,
    subdivide_edges,
)


def create_balcony_railing(bm, faces, prop, normal):
    vertical_edges = list({e for f in faces for e in filter_vertical_edges(f.edges, f.normal)})
    make_corner_posts(bm, vertical_edges, prop)
    for f in faces:
        make_fill(bm, f, prop)
    bmesh.ops.delete(bm, geom=faces, context="FACES")  # delete reference faces


def make_corner_posts(bm, edges, prop):
    for edge in edges:
        ret = bmesh.ops.duplicate(bm, geom=[edge])
        dup_edge = filter_geom(ret["geom"], BMEdge)[0]
        edge_to_cylinder(bm, dup_edge, prop.corner_post_width/2, Vector((1., 0., 0.)), fill=True)


def make_fill(bm, face, prop):
    add_facemap_for_groups((FaceMap.RAILING_POSTS, FaceMap.RAILING_RAILS))
    create_fill_posts(bm, face, prop)


@map_new_faces(FaceMap.RAILING_RAILS)
def create_fill_posts(bm, face, prop):
    # duplicate original face and resize
    ret = bmesh.ops.duplicate(bm, geom=[face])
    dup_face = filter_geom(ret["geom"], BMFace)[0]
    sorted_edges = sort_edges(dup_face.edges, Vector((0., 0., -1.)))
    top_edge = sorted_edges[0]
    bmesh.ops.translate(bm, verts=top_edge.verts, vec=Vector((0., 0., -1.))*prop.corner_post_width/2)

    # create railing top
    ret = bmesh.ops.duplicate(bm, geom=[top_edge])
    top_dup_edge = filter_geom(ret["geom"], BMEdge)[0]
    horizon = edge_vector(top_dup_edge).cross(Vector((0., 0., 1.)))
    up = edge_vector(top_dup_edge)
    up.rotate(Quaternion(horizon, math.pi/2).to_euler())
    edge_to_cylinder(bm, top_dup_edge, prop.corner_post_width/2, up)

    # create posts
    bottom_edge = sorted_edges[-1]
    n_posts = math.floor(top_edge.calc_length()*prop.post_fill.density/prop.post_fill.size)
    dir = edge_vector(top_edge)
    inner_edges = subdivide_edges(bm, [top_edge, bottom_edge], dir, widths=[1.]*(n_posts+1))
    for edge in inner_edges:
        ret = bmesh.ops.duplicate(bm, geom=[edge])
        dup_edge = filter_geom(ret["geom"], BMEdge)[0]
        up = face.normal
        edge_to_cylinder(bm, dup_edge, prop.post_fill.size/2, up)

    # delete duplicated faces
    dup_faces = list({f for e in inner_edges for f in e.link_faces})
    bmesh.ops.delete(bm, geom=dup_faces, context="FACES")


def edge_to_cylinder(bm, edge, radius, up, n=4, fill=False):
    edge_vec = edge_vector(edge)
    theta = (n-2)*math.pi/n
    length = 2 * radius * math.tan(theta/2)
    
    dir = up.copy()
    dir.rotate(Quaternion(edge_vec, -math.pi+theta/2).to_euler())
    bmesh.ops.translate(bm, verts=edge.verts, vec=dir*radius/math.sin(theta/2))
    all_verts = [v for v in edge.verts]
    dir.rotate(Quaternion(edge_vec, math.pi-theta/2).to_euler())
    for i in range(0, n):
        ret = bmesh.ops.extrude_edge_only(bm, edges=[edge])
        edge = filter_geom(ret["geom"], BMEdge)[0]
        bmesh.ops.translate(bm, verts=edge.verts, vec=dir*length)
        dir.rotate(Quaternion(edge_vec, math.radians(360/n)).to_euler())
        all_verts += edge.verts
    
    bmesh.ops.remove_doubles(bm, verts=all_verts, dist=0.001)

    if fill:  # fill holes
        valid_verts = [v for v in all_verts if v.is_valid]
        sorted_edges = sort_edges({e for v in valid_verts for e in v.link_edges}, edge_vec)
        top_edges = sorted_edges[-n:]
        bottom_edges = sorted_edges[:n]
        bmesh.ops.holes_fill(bm, edges=top_edges)
        bmesh.ops.holes_fill(bm, edges=bottom_edges)
