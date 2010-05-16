# add_mesh_gear.py (c) 2009, 2010 Michel J. Anders (varkenvarken)
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****


bl_addon_info = {
    'name': 'Add Mesh: Gears',
    'author': 'Michel J. Anders (varkenvarken)',
    'version': '2.4.1',
    'blender': (2, 5, 3),
    'location': 'View3D > Add > Mesh > Gears ',
    'description': 'Adds a mesh Gear to the Add Mesh menu',
    'url': 'http://wiki.blender.org/index.php/Extensions:2.5/Py/' \
        'Scripts/Add_Mesh/Add_Gear',
    'category': 'Add Mesh'}

"""
What was needed to port it from 2.49 -> 2.50 alpha 0?

The basic functions that calculate the geometry (verts and faces) are mostly
unchanged (add_tooth, add_spoke, add_gear)

Also, the vertex group API is changed a little bit but the concepts
are the same:
=========
vertexgroup = ob.add_vertex_group('NAME_OF_VERTEXGROUP')
for i in vertexgroup_vertex_indices:
    ob.add_vertex_to_group(i, vertexgroup, weight, 'ADD')
=========

Now for some reason the name does not 'stick' and we have to set it this way:
vertexgroup.name = 'NAME_OF_VERTEXGROUP'

Conversion to 2.50 also meant we could simply do away with our crude user
interface.
Just definining the appropriate properties in the AddGear() operator will
display the properties in the Blender GUI with the added benefit of making
it interactive: changing a property will redo the AddGear() operator providing
the user with instant feedback.

Finally we had to convert/throw away some print statements to print functions
as Blender nows uses Python 3.x

The code to actually implement the AddGear() function is mostly copied from
add_mesh_torus() (distributed with Blender).
"""

import bpy
import mathutils
from math import *
from bpy.props import *

# calculates the matrix for the new object
# depending on user pref
def align_matrix(context):
    loc = mathutils.TranslationMatrix(context.scene.cursor_location)
    obj_align = context.user_preferences.edit.object_align
    if (context.space_data.type == 'VIEW_3D'
        and obj_align == 'VIEW'):
        rot = context.space_data.region_3d.view_matrix.rotation_part().invert().resize4x4()
    else:
        rot = mathutils.Matrix()
    align_matrix = loc * rot
    return align_matrix

# Stores the values of a list of properties and the
# operator id in a property group ('recall_op') inside the object.
# Could (in theory) be used for non-objects.
# Note: Replaces any existing property group with the same name!
# ob ... Object to store the properties in.
# op ... The operator that should be used.
# op_args ... A dictionary with valid Blender
#             properties (operator arguments/parameters).
def store_recall_properties(ob, op, op_args):
    if ob and op and op_args:
        recall_properties = {}

        # Add the operator identifier and op parameters to the properties.
        recall_properties['op'] = op.bl_idname
        recall_properties['args'] = op_args

        # Store new recall properties.
        ob['recall'] = recall_properties


# Create a new mesh (object) from verts/edges/faces.
# verts/edges/faces ... List of vertices/edges/faces for the
#                       new mesh (as used in from_pydata).
# name ... Name of the new mesh (& object).
# edit ... Replace existing mesh data.
# Note: Using "edit" will destroy/delete existing mesh data.
def create_mesh_object(context, verts, edges, faces, name, edit, align_matrix):
    scene = context.scene
    obj_act = scene.objects.active

    # Can't edit anything, unless we have an active obj.
    if edit and not obj_act:
        return None

    # Create new mesh
    mesh = bpy.data.meshes.new(name)

    # Make a mesh from a list of verts/edges/faces.
    mesh.from_pydata(verts, edges, faces)

    # Update mesh geometry after adding stuff.
    mesh.update()

    # Deselect all objects.
    bpy.ops.object.select_all(action='DESELECT')

    if edit:
        # Replace geometry of existing object

        # Use the active obj and select it.
        ob_new = obj_act
        ob_new.selected = True

        if obj_act.mode == 'OBJECT':
            # Get existing mesh datablock.
            old_mesh = ob_new.data

            # Set object data to nothing
            ob_new.data = None

            # Clear users of existing mesh datablock.
            old_mesh.user_clear()

            # Remove old mesh datablock if no users are left.
            if (old_mesh.users == 0):
                bpy.data.meshes.remove(old_mesh)

            # Assign new mesh datablock.
            ob_new.data = mesh

    else:
        # Create new object
        ob_new = bpy.data.objects.new(name, mesh)

        # Link new object to the given scene and select it.
        scene.objects.link(ob_new)
        ob_new.selected = True

        # Place the object at the 3D cursor location.
        # apply viewRotaion
        ob_new.matrix = align_matrix


    if obj_act and obj_act.mode == 'EDIT':
        if not edit:
            # We are in EditMode, switch to ObjectMode.
            bpy.ops.object.mode_set(mode='OBJECT')

            # Select the active object as well.
            obj_act.selected = True

            # Apply location of new object.
            scene.update()

            # Join new object into the active.
            bpy.ops.object.join()

            # Switching back to EditMode.
            bpy.ops.object.mode_set(mode='EDIT')

            ob_new = obj_act

    else:
        # We are in ObjectMode.
        # Make the new object the active one.
        scene.objects.active = ob_new

    return ob_new


# A very simple "bridge" tool.
# Connects two equally long vertex rows with faces.
# Returns a list of the new faces (list of  lists)
#
# vertIdx1 ... First vertex list (list of vertex indices).
# vertIdx2 ... Second vertex list (list of vertex indices).
# closed ... Creates a loop (first & last are closed).
# flipped ... Invert the normal of the face(s).
#
# Note: You can set vertIdx1 to a single vertex index to create
#       a fan/star of faces.
# Note: If both vertex idx list are the same length they have
#       to have at least 2 vertices.
def createFaces(vertIdx1, vertIdx2, closed=False, flipped=False):
    faces = []

    if not vertIdx1 or not vertIdx2:
        return None

    if len(vertIdx1) < 2 and len(vertIdx2) < 2:
        return None

    fan = False
    if (len(vertIdx1) != len(vertIdx2)):
        if (len(vertIdx1) == 1 and len(vertIdx2) > 1):
            fan = True
        else:
            return None

    total = len(vertIdx2)

    if closed:
        # Bridge the start with the end.
        if flipped:
            face = [
                vertIdx1[0],
                vertIdx2[0],
                vertIdx2[total - 1]]
            if not fan:
                face.append(vertIdx1[total - 1])
            faces.append(face)

        else:
            face = [vertIdx2[0], vertIdx1[0]]
            if not fan:
                face.append(vertIdx1[total - 1])
            face.append(vertIdx2[total - 1])
            faces.append(face)

    # Bridge the rest of the faces.
    for num in range(total - 1):
        if flipped:
            if fan:
                face = [vertIdx2[num], vertIdx1[0], vertIdx2[num + 1]]
            else:
                face = [vertIdx2[num], vertIdx1[num],
                    vertIdx1[num + 1], vertIdx2[num + 1]]
            faces.append(face)
        else:
            if fan:
                face = [vertIdx1[0], vertIdx2[num], vertIdx2[num + 1]]
            else:
                face = [vertIdx1[num], vertIdx2[num],
                    vertIdx2[num + 1], vertIdx1[num + 1]]
            faces.append(face)

    return faces


# Calculate the vertex coordinates for a single
# section of a gear tooth.
# Returns 4 lists of vertex coords (list of tuples):
#  *-*---*---*	(1.) verts_inner_base
#  | |   |   |
#  *-*---*---*	(2.) verts_outer_base
#    |   |   |
#    *---*---*	(3.) verts_middle_tooth
#     \  |  /
#      *-*-*	(4.) verts_tip_tooth
#
# a
# t
# d
# radius
# Ad
# De
# base
# p_angle
# rack
# crown
def add_tooth(a, t, d, radius, Ad, De, base, p_angle, rack=0, crown=0.0):
    A = [a, a + t / 4, a + t / 2, a + 3 * t / 4]
    C = [cos(i) for i in A]
    S = [sin(i) for i in A]

    Ra = radius + Ad
    Rd = radius - De
    Rb = Rd - base

    # Pressure angle calc
    O = Ad * tan(p_angle)
    p_angle = atan(O / Ra)

    if radius < 0:
        p_angle = -p_angle

    if rack:
        S = [sin(t / 4) * I for I in range(-2, 3)]
        Sp = [0, sin(-t / 4 + p_angle), 0, sin(t / 4 - p_angle)]

        verts_inner_base = [(Rb, radius * S[I], d) for I in range(4)]
        verts_outer_base = [(Rd, radius * S[I], d) for I in range(4)]
        verts_middle_tooth = [(radius, radius * S[I], d) for I in range(1, 4)]
        verts_tip_tooth = [(Ra, radius * Sp[I], d) for I in range(1, 4)]

    else:
        Cp = [
            0,
            cos(a + t / 4 + p_angle),
            cos(a + t / 2),
            cos(a + 3 * t / 4 - p_angle)]
        Sp = [0,
            sin(a + t / 4 + p_angle),
            sin(a + t / 2),
            sin(a + 3 * t / 4 - p_angle)]

        verts_inner_base = [(Rb * C[I], Rb * S[I], d)
            for I in range(4)]
        verts_outer_base = [(Rd * C[I], Rd * S[I], d)
            for I in range(4)]
        verts_middle_tooth = [(radius * C[I], radius * S[I], d + crown / 3)
            for I in range(1, 4)]
        verts_tip_tooth = [(Ra * Cp[I], Ra * Sp[I], d + crown)
            for I in range(1, 4)]

    return (verts_inner_base, verts_outer_base,
        verts_middle_tooth, verts_tip_tooth)


# EXPERIMENTAL Calculate the vertex coordinates for a single
# section of a gearspoke.
# Returns them as a list of tuples.
#
# a
# t
# d
# radius
# De
# base
# s
# w
# l
# gap
# width
#
# @todo Finish this.
def add_spoke(a, t, d, radius, De, base, s, w, l, gap=0, width=19):
    Rd = radius - De
    Rb = Rd - base
    Rl = Rb

    verts = []
    edgefaces = []
    edgefaces2 = []
    sf = []

    if not gap:
        for N in range(width, 1, -2):
            edgefaces.append(len(verts))
            ts = t / 4
            tm = a + 2 * ts
            te = asin(w / Rb)
            td = te - ts
            t4 = ts + td * (width - N) / (width - 3.0)
            A = [tm + (i - int(N / 2)) * t4 for i in range(N)]
            C = [cos(i) for i in A]
            S = [sin(i) for i in A]

            verts.extend([(Rb * I, Rb * J, d) for (I, J) in zip(C, S)])
            edgefaces2.append(len(verts) - 1)

            Rb = Rb - s

        n = 0
        for N in range(width, 3, -2):
            sf.extend([(i + n, i + 1 + n, i + 2 + n, i + N + n)
                for i in range(0, N - 1, 2)])
            sf.extend([(i + 2 + n, i + N + n, i + N + 1 + n, i + N + 2 + n)
                for i in range(0, N - 3, 2)])

            n = n + N

    return verts, edgefaces, edgefaces2, sf


# Create gear geometry.
# Returns:
# * A list of vertices (list of tuples)
# * A list of faces (list of lists)
# * A list (group) of vertices of the tip (list of vertex indices).
# * A list (group) of vertices of the valley (list of vertex indices).
#
# teethNum ... Number of teeth on the gear.
# radius ... Radius of the gear, negative for crown gear
# Ad ... Addendum, extent of tooth above radius.
# De ... Dedendum, extent of tooth below radius.
# base ... Base, extent of gear below radius.
# p_angle ... Pressure angle. Skewness of tooth tip. (radiant)
# width ... Width, thickness of gear.
# skew ... Skew of teeth. (radiant)
# conangle ... Conical angle of gear. (radiant)
# rack
# crown ... Inward pointing extend of crown teeth.
#
# inner radius = radius - (De + base)
def add_gear(teethNum, radius, Ad, De, base, p_angle,
    width=1, skew=0, conangle=0, rack=0, crown=0.0):

    if teethNum < 2:
        return None, None, None, None

    t = 2 * pi / teethNum

    if rack:
        teethNum = 1

    scale = (radius - 2 * width * tan(conangle)) / radius

    verts = []
    faces = []
    vgroup_top = []  # Vertex group of top/tip? vertices.
    vgroup_valley = []  # Vertex group of valley vertices

    verts_bridge_prev = []
    for toothCnt in range(teethNum):
        a = toothCnt * t

        verts_bridge_start = []
        verts_bridge_end = []

        verts_outside_top = []
        verts_outside_bottom = []
        for (s, d, c, top) \
            in [(0, -width, 1, True), \
            (skew, width, scale, False)]:

            verts1, verts2, verts3, verts4 = add_tooth(a + s, t, d,
                radius * c, Ad * c, De * c, base * c, p_angle,
                rack, crown)

            vertsIdx1 = list(range(len(verts), len(verts) + len(verts1)))
            verts.extend(verts1)
            vertsIdx2 = list(range(len(verts), len(verts) + len(verts2)))
            verts.extend(verts2)
            vertsIdx3 = list(range(len(verts), len(verts) + len(verts3)))
            verts.extend(verts3)
            vertsIdx4 = list(range(len(verts), len(verts) + len(verts4)))
            verts.extend(verts4)

            verts_outside = []
            verts_outside.extend(vertsIdx2[:2])
            verts_outside.append(vertsIdx3[0])
            verts_outside.extend(vertsIdx4)
            verts_outside.append(vertsIdx3[-1])
            verts_outside.append(vertsIdx2[-1])

            if top:
                #verts_inside_top = vertsIdx1
                verts_outside_top = verts_outside

                verts_bridge_start.append(vertsIdx1[0])
                verts_bridge_start.append(vertsIdx2[0])
                verts_bridge_end.append(vertsIdx1[-1])
                verts_bridge_end.append(vertsIdx2[-1])

            else:
                #verts_inside_bottom = vertsIdx1
                verts_outside_bottom = verts_outside

                verts_bridge_start.append(vertsIdx2[0])
                verts_bridge_start.append(vertsIdx1[0])
                verts_bridge_end.append(vertsIdx2[-1])
                verts_bridge_end.append(vertsIdx1[-1])

            # Valley = first 2 vertices of outer base:
            vgroup_valley.extend(vertsIdx2[:1])
            # Top/tip vertices:
            vgroup_top.extend(vertsIdx4)

            faces_tooth_middle_top = createFaces(vertsIdx2[1:], vertsIdx3,
                flipped=top)
            faces_tooth_outer_top = createFaces(vertsIdx3, vertsIdx4,
                flipped=top)

            faces_base_top = createFaces(vertsIdx1, vertsIdx2, flipped=top)
            faces.extend(faces_base_top)

            faces.extend(faces_tooth_middle_top)
            faces.extend(faces_tooth_outer_top)

        #faces_inside = createFaces(verts_inside_top, verts_inside_bottom)
        #faces.extend(faces_inside)

        faces_outside = createFaces(verts_outside_top, verts_outside_bottom,
            flipped=True)
        faces.extend(faces_outside)

        if toothCnt == 0:
            verts_bridge_first = verts_bridge_start

        # Bridge one tooth to the next
        if verts_bridge_prev:
            faces_bridge = createFaces(verts_bridge_prev, verts_bridge_start)
                            #, closed=True (for "inside" faces)
            faces.extend(faces_bridge)

        # Remember "end" vertices for next tooth.
        verts_bridge_prev = verts_bridge_end

    # Bridge the first to the last tooth.
    faces_bridge_f_l = createFaces(verts_bridge_prev, verts_bridge_first)
                        #, closed=True (for "inside" faces)
    faces.extend(faces_bridge_f_l)

    return verts, faces, vgroup_top, vgroup_valley


# Create spokes geometry.
# Returns:
# * A list of vertices (list of tuples)
# * A list of faces (list of lists)
#
# teethNum ... Number of teeth on the gear.
# radius ... Radius of the gear, negative for crown gear
# De ... Dedendum, extent of tooth below radius.
# base ... Base, extent of gear below radius.
# width ... Width, thickness of gear.
# conangle ... Conical angle of gear. (radiant)
# rack
# spoke
# spbevel
# spwidth
# splength
# spresol
#
# @todo Finish this
# @todo Create a function that takes a "Gear" and creates a
#       matching "Gear Spokes" object.
def add_spokes(teethNum, radius, De, base, width=1, conangle=0, rack=0,
    spoke=3, spbevel=0.1, spwidth=0.2, splength=1.0, spresol=9):

    if teethNum < 2:
        return None, None, None, None

    if spoke < 2:
        return None, None, None, None

    t = 2 * pi / teethNum

    if rack:
        teethNum = 1

    scale = (radius - 2 * width * tan(conangle)) / radius

    verts = []
    faces = []

    c = scale   # debug

    fl = len(verts)
    for toothCnt in range(teethNum):
        a = toothCnt * t
        s = 0       # For test

        if toothCnt % spoke == 0:
            for d in (-width, width):
                sv, edgefaces, edgefaces2, sf = add_spoke(a + s, t, d,
                    radius * c, De * c, base * c,
                    spbevel, spwidth, splength, 0, spresol)
                verts.extend(sv)
                faces.extend([[j + fl for j in i] for i in sf])
                fl += len(sv)

            d1 = fl - len(sv)
            d2 = fl - 2 * len(sv)

            faces.extend([(i + d2, j + d2, j + d1, i + d1)
                for (i, j) in zip(edgefaces[:-1], edgefaces[1:])])
            faces.extend([(i + d2, j + d2, j + d1, i + d1)
                for (i, j) in zip(edgefaces2[:-1], edgefaces2[1:])])

        else:
            for d in (-width, width):
                sv, edgefaces, edgefaces2, sf = add_spoke(a + s, t, d,
                    radius * c, De * c, base * c,
                    spbevel, spwidth, splength, 1, spresol)

                verts.extend(sv)
                fl += len(sv)

            d1 = fl - len(sv)
            d2 = fl - 2 * len(sv)

            faces.extend([[i + d2, i + 1 + d2, i + 1 + d1, i + d1]
                for (i) in range(0, 3)])
            faces.extend([[i + d2, i + 1 + d2, i + 1 + d1, i + d1]
                for (i) in range(5, 8)])

    return verts, faces


# Create worm geometry.
# Returns:
# * A list of vertices
# * A list of faces
# * A list (group) of vertices of the tip
# * A list (group) of vertices of the valley
#
# teethNum ... Number of teeth on the worm
# radius ... Radius of the gear, negative for crown gear
# Ad ... Addendum, extent of tooth above radius.
# De ... Dedendum, extent of tooth below radius.
# p_angle ... Pressure angle. Skewness of tooth tip. (radiant)
# width ... Width, thickness of gear.
# crown ... Inward pointing extend of crown teeth.
#
# @todo: Fix teethNum. Some numbers are not possible yet.
# @todo: Create start & end geoemtry (closing faces)
def add_worm(teethNum, rowNum, radius, Ad, De, p_angle,
    width=1, skew=radians(11.25), crown=0.0):

    worm = teethNum
    teethNum = 24

    t = 2 * pi / teethNum

    verts = []
    faces = []
    vgroup_top = []  # Vertex group of top/tip? vertices.
    vgroup_valley = []  # Vertex group of valley vertices

    #width = width / 2.0

    edgeloop_prev = []
    for Row in range(rowNum):
        edgeloop = []

        for toothCnt in range(teethNum):
            a = toothCnt * t

            s = Row * skew
            d = Row * width
            c = 1

            isTooth = False
            if toothCnt % (teethNum / worm) != 0:
                # Flat
                verts1, verts2, verts3, verts4 = add_tooth(a + s, t, d,
                    radius - De, 0.0, 0.0, 0, p_angle)

                # Ignore other verts than the "other base".
                verts1 = verts3 = verts4 = []

            else:
                # Tooth
                isTooth = True
                verts1, verts2, verts3, verts4 = add_tooth(a + s, t, d,
                    radius * c, Ad * c, De * c, 0 * c, p_angle, 0, crown)

                # Remove various unneeded verts (if we are "inside" the tooth)
                del(verts2[2])  # Central vertex in the base of the tooth.
                del(verts3[1])  # Central vertex in the middle of the tooth.

            vertsIdx2 = list(range(len(verts), len(verts) + len(verts2)))
            verts.extend(verts2)
            vertsIdx3 = list(range(len(verts), len(verts) + len(verts3)))
            verts.extend(verts3)
            vertsIdx4 = list(range(len(verts), len(verts) + len(verts4)))
            verts.extend(verts4)

            if isTooth:
                verts_current = []
                verts_current.extend(vertsIdx2[:2])
                verts_current.append(vertsIdx3[0])
                verts_current.extend(vertsIdx4)
                verts_current.append(vertsIdx3[-1])
                verts_current.append(vertsIdx2[-1])

                # Valley = first 2 vertices of outer base:
                vgroup_valley.extend(vertsIdx2[:1])
                # Top/tip vertices:
                vgroup_top.extend(vertsIdx4)

            else:
                # Flat
                verts_current = vertsIdx2

                # Valley - all of them.
                vgroup_valley.extend(vertsIdx2)

            edgeloop.extend(verts_current)

        # Create faces between rings/rows.
        if edgeloop_prev:
            faces_row = createFaces(edgeloop, edgeloop_prev, closed=True)
            faces.extend(faces_row)

        # Remember last ring/row of vertices for next ring/row iteration.
        edgeloop_prev = edgeloop

    return verts, faces, vgroup_top, vgroup_valley


class AddGear(bpy.types.Operator):
    '''Add a gear mesh.'''
    bl_idname = "mesh.primitive_gear"
    bl_label = "Add Gear"
    bl_options = {'REGISTER', 'UNDO'}

    # edit - Whether to add or update.
    edit = BoolProperty(name="",
        description="",
        default=False,
        options={'HIDDEN'})
    number_of_teeth = IntProperty(name="Number of Teeth",
        description="Number of teeth on the gear",
        min=2,
        max=265,
        default=12)
    radius = FloatProperty(name="Radius",
        description="Radius of the gear, negative for crown gear",
        min=-100.0,
        max=100.0,
        default=1.0)
    addendum = FloatProperty(name="Addendum",
        description="Addendum, extent of tooth above radius",
        min=0.01,
        max=100.0,
        default=0.1)
    dedendum = FloatProperty(name="Dedendum",
        description="Dedendum, extent of tooth below radius",
        min=0.0,
        max=100.0,
        default=0.1)
    angle = FloatProperty(name="Pressure Angle",
        description="Pressure angle, skewness of tooth tip (degrees)",
        min=0.0,
        max=45.0,
        default=20.0)
    base = FloatProperty(name="Base",
        description="Base, extent of gear below radius",
        min=0.0,
        max=100.0,
        default=0.2)
    width = FloatProperty(name="Width",
        description="Width, thickness of gear",
        min=0.05,
        max=100.0,
        default=0.2)
    skew = FloatProperty(name="Skewness",
        description="Skew of teeth (degrees)",
        min=-90.0,
        max=90.0,
        default=0.0)
    conangle = FloatProperty(name="Conical angle",
        description="Conical angle of gear (degrees)",
        min=0.0,
        max=90.0,
        default=0.0)
    crown = FloatProperty(name="Crown",
        description="Inward pointing extend of crown teeth",
        min=0.0,
        max=100.0,
        default=0.0)
    align_matrix = mathutils.Matrix()

    def draw(self, context):
        props = self.properties
        layout = self.layout
        box = layout.box()
        box.prop(props, 'number_of_teeth')
        box = layout.box()
        box.prop(props, 'radius')
        box.prop(props, 'width')
        box.prop(props, 'base')
        box = layout.box()
        box.prop(props, 'dedendum')
        box.prop(props, 'addendum')
        box = layout.box()
        box.prop(props, 'angle')
        box.prop(props, 'skew')
        box.prop(props, 'conangle')
        box.prop(props, 'crown')


    def execute(self, context):
        props = self.properties

        verts, faces, verts_tip, verts_valley = add_gear(
            props.number_of_teeth,
            props.radius,
            props.addendum,
            props.dedendum,
            props.base,
            radians(props.angle),
            width=props.width,
            skew=radians(props.skew),
            conangle=radians(props.conangle),
            crown=props.crown)

        # Actually create the mesh object from this geometry data.
        obj = create_mesh_object(context, verts, [], faces, "Gear", props.edit, self.align_matrix)

        # Store 'recall' properties in the object.
        recall_args_list = {
            "edit": True,
            "number_of_teeth": props.number_of_teeth,
            "radius": props.radius,
            "addendum": props.addendum,
            "dedendum": props.dedendum,
            "angle": props.angle,
            "base": props.base,
            "width": props.width,
            "skew": props.skew,
            "conangle": props.conangle,
            "crown": props.crown}
        store_recall_properties(obj, self, recall_args_list)

        # Create vertex groups from stored vertices.
        tipGroup = obj.add_vertex_group('Tips')
        for vert in verts_tip:
            obj.add_vertex_to_group(vert, tipGroup, 1.0, 'ADD')

        valleyGroup = obj.add_vertex_group('Valleys')
        for vert in verts_valley:
            obj.add_vertex_to_group(vert, valleyGroup, 1.0, 'ADD')

        return {'FINISHED'}

    def invoke(self, context, event):
        self.align_matrix = align_matrix(context)
        self.execute(context)
        return {'FINISHED'}

class AddWormGear(bpy.types.Operator):
    '''Add a worm gear mesh.'''
    bl_idname = "mesh.primitive_worm_gear"
    bl_label = "Add Worm Gear"
    bl_options = {'REGISTER', 'UNDO'}

    # edit - Whether to add or update.
    edit = BoolProperty(name="",
        description="",
        default=False,
        options={'HIDDEN'})
    number_of_teeth = IntProperty(name="Number of Teeth",
        description="Number of teeth on the gear",
        min=2,
        max=265,
        default=12)
    number_of_rows = IntProperty(name="Number of Rows",
        description="Number of rows on the worm gear",
        min=2,
        max=265,
        default=32)
    radius = FloatProperty(name="Radius",
        description="Radius of the gear, negative for crown gear",
        min=-100.0,
        max=100.0,
        default=1.0)
    addendum = FloatProperty(name="Addendum",
        description="Addendum, extent of tooth above radius",
        min=0.01,
        max=100.0,
        default=0.1)
    dedendum = FloatProperty(name="Dedendum",
        description="Dedendum, extent of tooth below radius",
        min=0.0,
        max=100.0,
        default=0.1)
    angle = FloatProperty(name="Pressure Angle",
        description="Pressure angle, skewness of tooth tip (degrees)",
        min=0.0,
        max=45.0,
        default=20.0)
    row_height = FloatProperty(name="Row Height",
        description="Height of each Row",
        min=0.05,
        max=100.0,
        default=0.2)
    skew = FloatProperty(name="Skewness per Row",
        description="Skew of each row (degrees)",
        min=-90.0,
        max=90.0,
        default=11.25)
    crown = FloatProperty(name="Crown",
        description="Inward pointing extend of crown teeth",
        min=0.0,
        max=100.0,
        default=0.0)
    align_matrix = mathutils.Matrix()

    def draw(self, context):
        props = self.properties
        layout = self.layout
        box = layout.box()
        box.prop(props, 'number_of_teeth')
        box.prop(props, 'number_of_rows')
        box.prop(props, 'radius')
        box.prop(props, 'row_height')
        box = layout.box()
        box.prop(props, 'addendum')
        box.prop(props, 'dedendum')
        box = layout.box()
        box.prop(props, 'angle')
        box.prop(props, 'skew')
        box.prop(props, 'crown')

    def execute(self, context):
        props = self.properties

        verts, faces, verts_tip, verts_valley = add_worm(
            props.number_of_teeth,
            props.number_of_rows,
            props.radius,
            props.addendum,
            props.dedendum,
            radians(props.angle),
            width=props.row_height,
            skew=radians(props.skew),
            crown=props.crown)

        # Actually create the mesh object from this geometry data.
        obj = create_mesh_object(context, verts, [], faces, "Worm Gear",
            props.edit, self.align_matrix)

        # Store 'recall' properties in the object.
        recall_args_list = {
            "edit": True,
            "number_of_teeth": props.number_of_teeth,
            "number_of_rows": props.number_of_rows,
            "radius": props.radius,
            "addendum": props.addendum,
            "dedendum": props.dedendum,
            "angle": props.angle,
            "row_height": props.row_height,
            "skew": props.skew,
            "crown": props.crown}
        store_recall_properties(obj, self, recall_args_list)

        # Create vertex groups from stored vertices.
        tipGroup = obj.add_vertex_group('Tips')
        for vert in verts_tip:
            obj.add_vertex_to_group(vert, tipGroup, 1.0, 'ADD')

        valleyGroup = obj.add_vertex_group('Valleys')
        for vert in verts_valley:
            obj.add_vertex_to_group(vert, valleyGroup, 1.0, 'ADD')

        return {'FINISHED'}

    def invoke(self, context, event):
        self.align_matrix = align_matrix(context)
        self.execute(context)
        return {'FINISHED'}

class INFO_MT_mesh_gears_add(bpy.types.Menu):
    # Define the "Gears" menu
    bl_idname = "INFO_MT_mesh_gears_add"
    bl_label = "Gears"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        layout.operator("mesh.primitive_gear",
            text="Gear")
        layout.operator("mesh.primitive_worm_gear",
            text="Worm")


# Define "Gears" menu
menu_func = (lambda self,
    context: self.layout.menu("INFO_MT_mesh_gears_add", icon="PLUGIN"))


def register():
    bpy.types.register(AddGear)
    bpy.types.register(AddWormGear)
    bpy.types.register(INFO_MT_mesh_gears_add)

    # Add "Gears" entry to the "Add Mesh" menu.
    bpy.types.INFO_MT_mesh_add.append(menu_func)


def unregister():
    bpy.types.unregister(AddGear)
    bpy.types.unregister(AddWormGear)
    bpy.types.unregister(INFO_MT_mesh_gears_add)

    # Remove "Gears" entry from the "Add Mesh" menu.
    bpy.types.INFO_MT_mesh_add.remove(menu_func)

if __name__ == "__main__":
    register()