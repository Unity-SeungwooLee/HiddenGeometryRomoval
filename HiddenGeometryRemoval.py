bl_info = {
    "name": "Hidden Geometry Removal",
    "author": "Seungwoo Lee",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > Hidden Removal",
    "description": "Removes geometry that is not visible from multiple camera positions",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy
import bmesh
import math
from mathutils import Vector
from bpy.props import IntProperty, FloatProperty, EnumProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy.utils import register_class, unregister_class


def create_camera_ring(row_angle, camera_heights, radius, prefix="Camera"):
    """
    Create cameras along a vertical spline at specified row angle
    """
    cameras = []
    for i, height_angle in enumerate(camera_heights):
        # Convert angles to radians
        height_rad = math.radians(height_angle)
        row_rad = math.radians(row_angle)
        
        # Calculate position on sphere
        height = radius * math.sin(height_rad)
        horizontal_radius = radius * math.cos(height_rad)
        x = horizontal_radius * math.cos(row_rad)
        y = horizontal_radius * math.sin(row_rad)
        z = height
        
        # Create camera
        cam_data = bpy.data.cameras.new(name=f"{prefix}.Row{row_angle:.0f}.{i+1}")
        cam_obj = bpy.data.objects.new(f"{prefix}.Row{row_angle:.0f}.{i+1}", cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)
        
        # Position camera
        cam_obj.location = (x, y, z)
        
        # Point camera to center (0,0,0)
        direction = cam_obj.location
        cam_obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        
        cameras.append(cam_obj)
    return cameras


def create_camera_setup(rows=4, cameras_per_row=4, sphere_radius=10):
    """
    Create cameras arranged in vertical splines around a sphere
    """
    # Calculate angles between rows
    row_angle_step = 360.0 / rows
    
    # Calculate camera height angles
    cameras_per_half = cameras_per_row // 2
    height_angle_step = 90.0 / (cameras_per_half + 1)
    height_angles = []
    
    # Generate positive and negative angles
    for i in range(cameras_per_half):
        angle = height_angle_step * (i + 1)
        height_angles.extend([angle, -angle])
    
    # Create cameras for each row
    all_cameras = []
    for i in range(rows):
        row_angle = i * row_angle_step
        row_cameras = create_camera_ring(row_angle, height_angles, sphere_radius)
        all_cameras.extend(row_cameras)
    
    return all_cameras


def select_visible_faces_multi_cameras(obj, cameras, precision):
    bpy.ops.object.mode_set(mode='OBJECT')
    scene = bpy.context.scene
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    for face in bm.faces:
        face.select = False

    for camera in cameras:
        cam_location = camera.matrix_world.translation
        cam_direction = camera.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        cam_fov = camera.data.angle if camera.data.type == 'PERSP' else math.radians(90.0)

        for face in bm.faces:
            if face.select:
                continue

            points_to_check = [obj.matrix_world @ face.calc_center_median()]
            
            if precision == 'HIGH':
                points_to_check.extend([obj.matrix_world @ vert.co for vert in face.verts])
                points_to_check.extend([(obj.matrix_world @ edge.verts[0].co + obj.matrix_world @ edge.verts[1].co) / 2 for edge in face.edges])

            for point in points_to_check:
                to_point = (point - cam_location).normalized()
                angle = to_point.angle(cam_direction)

                if angle < cam_fov / 2:
                    result = scene.ray_cast(
                        depsgraph=bpy.context.evaluated_depsgraph_get(),
                        origin=cam_location,
                        direction=to_point
                    )

                    if result[0]:
                        hit_distance = (result[1] - point).length
                        if hit_distance < 0.001:
                            face.select = True
                            break

    bm.to_mesh(mesh)
    bm.free()
    bpy.ops.object.mode_set(mode='EDIT')


def delete_invisible_faces():
    bpy.ops.mesh.hide(unselected=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='FACE')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='EDGE')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='VERT')
    bpy.ops.mesh.reveal()
    bpy.ops.object.mode_set(mode='OBJECT')


def delete_all_cameras():
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)


class HiddenRemovalProperties(PropertyGroup):
    rows: IntProperty(
        name="Number of Rows",
        description="Number of vertical splines around the sphere",
        default=4,
        min=2,
        max=12,
    )
    
    cameras_per_row: IntProperty(
        name="Cameras per Row",
        description="Number of cameras per vertical spline (must be even)",
        default=4,
        min=2,
        max=12,
        step=2
    )

    sphere_radius: FloatProperty(
        name="Camera Distance",
        description="Distance of cameras from the object center",
        default=10.0,
        min=0.1,
    )

    delete_select_mode: EnumProperty(
        name="Delete/Select Mode",
        description="Choose whether to delete the hidden geometry or select the outer geometry",
        items=[
            ('DELETE', "Delete", "Delete the hidden geometry"),
            ('OUTER_SELECT', "Outer Select", "Select the outer geometry"),
        ],
        default='DELETE',
    )

    precision_mode: EnumProperty(
        name="Precision",
        description="Choose the precision level",
        items=[
            ('HIGH', "High", "Use vertex and edge checks for high precision"),
            ('LOW', "Low", "Only use face center check for lower precision"),
        ],
        default='HIGH',
    )


class OBJECT_OT_hidden_geometry_removal(Operator):
    bl_idname = "object.hidden_geometry_removal"
    bl_label = "Remove Hidden Geometry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object")
            return {'CANCELLED'}

        props = context.scene.hidden_removal_props

        delete_all_cameras()
        cameras = create_camera_setup(props.rows, props.cameras_per_row, props.sphere_radius)
        select_visible_faces_multi_cameras(obj, cameras, props.precision_mode)

        if props.delete_select_mode == 'DELETE':
            delete_invisible_faces()

        delete_all_cameras()
        self.report({'INFO'}, f"Processed geometry using {len(cameras)} cameras")
        return {'FINISHED'}


class VIEW3D_PT_hidden_geometry_removal(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hidden Removal"
    bl_label = "Hidden Geometry Removal"

    def draw(self, context):
        layout = self.layout
        props = context.scene.hidden_removal_props

        # Warning text at the top
        box = layout.box()
        box.label(text="Select a mesh object first", icon='INFO')

        # Settings box
        box = layout.box()
        box.label(text="Settings")

        # Rows section
        col = box.column()
        col.label(text="Number of vertical camera splines")
        col.prop(props, "rows")
        col.separator()

        # Cameras per Row section
        col = box.column()
        col.label(text="Number of cameras per spline")
        col.prop(props, "cameras_per_row")
        col.separator()

        # Camera Distance section
        col = box.column()
        col.label(text="Should be larger than object dimensions")
        col.prop(props, "sphere_radius")
        col.separator()

        # Delete/Select Mode section
        col = box.column()
        col.prop(props, "delete_select_mode")
        col.separator()

        # Precision Mode section
        col = box.column()
        col.prop(props, "precision_mode")
        col.separator()
        
        # Remove Hidden Geometry button with double height
        row = box.row()
        row.scale_y = 2.0
        row.operator(OBJECT_OT_hidden_geometry_removal.bl_idname)


classes = (
    HiddenRemovalProperties,
    OBJECT_OT_hidden_geometry_removal,
    VIEW3D_PT_hidden_geometry_removal,
)


def register():
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.hidden_removal_props = bpy.props.PointerProperty(type=HiddenRemovalProperties)


def unregister():
    del bpy.types.Scene.hidden_removal_props
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()