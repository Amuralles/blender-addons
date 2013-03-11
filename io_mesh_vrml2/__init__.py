# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

bl_info = {
    "name": "VRML2 (Virtual Reality Modeling Language)",
    "author": "Campbell Barton",
    "blender": (2, 66, 0),
    "location": "File > Export",
    "description": "Exports the active mesh object to VRML2, supporting vertex and material colors",
    "warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/"
                "Scripts/Import-Export/VRML2",
    "tracker_url": "",
    "support": 'OFFICIAL',
    "category": "Import-Export"}

if "bpy" in locals():
    import imp
    if "export_vrml2" in locals():
        imp.reload(export_vrml2)


import os
import bpy
from bpy.props import CollectionProperty, StringProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper

class ExportPLY(bpy.types.Operator, ExportHelper):
    """Export a single object as a Stanford PLY with normals, """ \
    """colors and texture coordinates"""
    bl_idname = "export_mesh.ply"
    bl_label = "Export PLY"

    filename_ext = ".ply"
    filter_glob = StringProperty(default="*.ply", options={'HIDDEN'})

    use_mesh_modifiers = BoolProperty(
            name="Apply Modifiers",
            description="Apply Modifiers to the exported mesh",
            default=True,
            )
    use_colors = BoolProperty(
            name="Vertex Colors",
            description="Export the active vertex color layer",
            default=True)
    color_type = EnumProperty(
            name='Color',
            items=(
            ('MATERIAL', "Material Color", ""),
            ('VERTEX', "Vertex Color", "")),
            default='MATERIAL',
            )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None) and obj.type == 'MESH'

    def execute(self, context):
        filepath = self.filepath
        filepath = bpy.path.ensure_ext(filepath, self.filename_ext)
        from . import export_vrml2
        keywords = self.as_keywords(ignore=("check_existing", "filter_glob"))
        return export_vrml2.save(self, context, **keywords)

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.prop(self, "use_mesh_modifiers")
        row.prop(self, "use_colors")
        row = layout.row()
        row.active = self.use_colors
        row.prop(self, "color_type")


def menu_func_export(self, context):
    self.layout.operator(ExportPLY.bl_idname, text="VRML2 (.wrl)")


def register():
    bpy.utils.register_module(__name__)

    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_module(__name__)

    bpy.types.INFO_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
