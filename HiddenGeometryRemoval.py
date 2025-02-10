# hidden_removal_addon.py
bl_info = {
    "name": "Hidden Geometry Removal",
    "author": "Seungwoo Lee",
    "version": (0, 0, 1),
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
from bpy.props import IntProperty, FloatProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy.utils import register_class, unregister_class

# Your existing functions here
def create_camera_ring(num_cameras, radius, z_angle, rotation_offset=0, prefix="Camera"):
    """
    Create a ring of cameras at specified height and radius
    """
    height = radius * math.sin(math.radians(z_angle))
    ring_radius = radius * math.cos(math.radians(z_angle))
    cameras = []
    
    for i in range(num_cameras):
        angle = (2 * math.pi * i) / num_cameras + math.radians(rotation_offset)
        x = ring_radius * math.cos(angle)
        y = ring_radius * math.sin(angle)
        z = height
        
        cam_data = bpy.data.cameras.new(name=f"{prefix}.{i+1}")
        cam_obj = bpy.data.objects.new(f"{prefix}.{i+1}", cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)
        cam_obj.location = (x, y, z)
        
        direction = cam_obj.location
        cam_obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        
        cameras.append(cam_obj)
    
    return cameras

def create_camera_setup(num_total_cameras=8, sphere_radius=10):
    if num_total_cameras < 8:
        num_total_cameras = 8
    if num_total_cameras % 2 != 0:
        num_total_cameras += 1
    
    cameras_per_ring = num_total_cameras // 2
    upper_cameras = create_camera_ring(cameras_per_ring, sphere_radius, 45, 0, "UpperCam")
    lower_cameras = create_camera_ring(cameras_per_ring, sphere_radius, -45, 360/cameras_per_ring, "LowerCam")
    
    return upper_cameras + lower_cameras

def select_visible_faces_multi_cameras(obj, cameras):
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
            points_to_check.extend([obj.matrix_world @ vert.co for vert in face.verts])
            points_to_check.extend([(obj.matrix_world @ edge.verts[0].co + obj.matrix_world @ edge.verts[1].co) / 2 for edge in face.edges])
            
            for point in points_to_check:
                to_point = (point - cam_location).normalized()
                angle = to_point.angle(cam_direction)
                if angle < cam_fov/2:
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
    num_cameras: IntProperty(
        name="Number of Cameras",  # Added name back for side-by-side layout
        description="Total number of cameras to use (will be split between upper and lower rings)",
        default=8,
        min=8,
        max=64
    )
    
    sphere_radius: FloatProperty(
        name="Camera Distance",  # Added name back for side-by-side layout
        description="Distance of cameras from the object center",
        default=10.0,
        min=0.1
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
        cameras = create_camera_setup(props.num_cameras, props.sphere_radius)
        select_visible_faces_multi_cameras(obj, cameras)
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
        
        # Number of Cameras section
        col = box.column()
        col.label(text="Higher values preserve more geometric detail")
        col.prop(props, "num_cameras")
        col.separator()
        
        # Camera Distance section
        col = box.column()
        col.label(text="Should be larger than object dimensions")
        col.prop(props, "sphere_radius")
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