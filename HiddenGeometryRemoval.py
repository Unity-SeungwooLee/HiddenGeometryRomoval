bl_info = {
    "name": "Hidden Geometry Removal",
    "author": "Seungwoo Lee",
    "version": (0, 1, 3),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > Hidden Removal",
    "description": "Removes geometry that is not visible from multiple camera positions. Includes mesh merging options and experimental randomized face selection",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy
import bmesh
import math
import random
from mathutils import Vector
from bpy.props import IntProperty, FloatProperty, EnumProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy.utils import register_class, unregister_class


def get_or_create_camera_collection():
    """
    Get the 'Cameras' collection or create it if it doesn't exist
    """
    if "Cameras" in bpy.data.collections:
        return bpy.data.collections["Cameras"]
    
    # Create a new collection
    cam_collection = bpy.data.collections.new("Cameras")
    bpy.context.scene.collection.children.link(cam_collection)
    return cam_collection


def create_camera_ring(row_angle, camera_heights, radius, collection, prefix="Camera"):
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
        temp_name = f"{prefix}.Row{row_angle:.0f}.{i+1}"
        cam_data = bpy.data.cameras.new(name=temp_name)
        cam_obj = bpy.data.objects.new(temp_name, cam_data)
        
        # Add camera to the collection instead of scene collection
        collection.objects.link(cam_obj)
        
        # Position camera
        cam_obj.location = (x, y, z)
        
        # Point camera to center (0,0,0)
        direction = cam_obj.location
        cam_obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        
        cameras.append(cam_obj)
    return cameras


def create_camera_setup(rows=4, cameras_per_row=4, sphere_radius=10, keep_cameras=False):
    """
    Create cameras arranged in vertical splines around a sphere
    """
    # Determine which collection to use
    if keep_cameras:
        collection = get_or_create_camera_collection()
    else:
        collection = bpy.context.scene.collection
    
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
        row_cameras = create_camera_ring(row_angle, height_angles, sphere_radius, collection)
        all_cameras.extend(row_cameras)
    
    return all_cameras


def are_faces_similar(face1, face2, max_angle_diff):
    """
    Check if two faces are similar based on their normal angle
    """
    angle = abs(face1.normal.angle(face2.normal))
    return math.degrees(angle) <= max_angle_diff


def select_visible_faces_multi_cameras(obj, cameras, precision, experimental, sampling_ratio, flatness_angle):
    bpy.ops.object.mode_set(mode='OBJECT')
    scene = bpy.context.scene
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    for face in bm.faces:
        face.select = False

    # Calculate number of faces to sample
    total_faces = len(bm.faces)
    
    if experimental:
        sample_count = max(1, int(total_faces * (sampling_ratio / 100)))
        # Randomly select initial faces to check
        initial_faces = random.sample(list(bm.faces), sample_count)
    else:
        # Check all faces if not in experimental mode
        initial_faces = list(bm.faces)
    
    for camera in cameras:
        cam_location = camera.matrix_world.translation
        cam_direction = camera.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        cam_fov = camera.data.angle if camera.data.type == 'PERSP' else math.radians(90.0)

        # Faces to check this iteration (starts with initial sample)
        faces_to_check = set(initial_faces)
        checked_faces = set()

        while faces_to_check:
            current_face = faces_to_check.pop()
            
            # Skip if already checked or selected
            if current_face in checked_faces or current_face.select:
                continue
            
            checked_faces.add(current_face)

            points_to_check = [obj.matrix_world @ current_face.calc_center_median()]
            
            if precision == 'HIGH':
                points_to_check.extend([obj.matrix_world @ vert.co for vert in current_face.verts])
                points_to_check.extend([(obj.matrix_world @ edge.verts[0].co + obj.matrix_world @ edge.verts[1].co) / 2 for edge in current_face.edges])

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
                            current_face.select = True

                            # Expand to similar faces based on flatness
                            if experimental:
                                for neighbor in current_face.verts:
                                    for linked_face in neighbor.link_faces:
                                        if (linked_face not in checked_faces and 
                                            not linked_face.select and 
                                            are_faces_similar(current_face, linked_face, flatness_angle)):
                                            faces_to_check.add(linked_face)
                            break

    bm.to_mesh(mesh)
    bm.free()
    bpy.ops.object.mode_set(mode='EDIT')
    
    return total_faces


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
    # First try to find the Cameras collection
    if "Cameras" in bpy.data.collections:
        cam_collection = bpy.data.collections["Cameras"]
        # Remove all camera objects from the collection
        for obj in list(cam_collection.objects):
            if obj.type == 'CAMERA':
                bpy.data.objects.remove(obj, do_unlink=True)
        # Also remove the collection itself
        bpy.data.collections.remove(cam_collection)
    
    # Also look for any cameras in the scene that might not be in the collection
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)


def merge_all_meshes():
    """
    Merge all mesh objects in the scene into a single object
    """
    # Deselect all objects first
    bpy.ops.object.select_all(action='DESELECT')
    
    # Get all mesh objects in the scene
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    if not mesh_objects:
        return None
    
    # Make the first mesh object the active object
    bpy.context.view_layer.objects.active = mesh_objects[0]
    mesh_objects[0].select_set(True)
    
    # Join all other mesh objects to the first one
    for obj in mesh_objects[1:]:
        obj.select_set(True)
    
    bpy.ops.object.join()
    
    return bpy.context.active_object


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
    
    keep_cameras: BoolProperty(
        name="Keep Cameras",
        description="Keep the created cameras in a 'Cameras' collection",
        default=False,
    )

    experimental: BoolProperty(
        name="Experimental",
        description="Enable experimental randomized face selection and similar face expansion",
        default=False,
    )

    sampling_ratio: IntProperty(
        name="Face Sampling Ratio",
        description="Percentage of faces to randomly sample for visibility check",
        default=30,
        min=1,
        max=100,
        subtype='PERCENTAGE'
    )

    flatness_angle: FloatProperty(
        name="Flatness Angle",
        description="Maximum angle difference for considering faces similar",
        default=30.0,
        min=10.0,
        max=90.0,
    )
    
    merge_meshes: BoolProperty(
        name="Merge Meshes",
        description="Merge all mesh objects in the scene before processing",
        default=True,
    )

    merge_by_distance: BoolProperty(
        name="Merge by Distance",
        description="Merge vertices that are very close to each other",
        default=True,
    )


class OBJECT_OT_hidden_geometry_removal(Operator):
    bl_idname = "object.hidden_geometry_removal"
    bl_label = "Remove Hidden Geometry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.hidden_removal_props
        
        # Merge meshes if option is checked
        original_objects = []
        merged_object = None
        if props.merge_meshes:
            # Store original objects to restore later if needed
            original_objects = list(bpy.context.selected_objects)
            merged_object = merge_all_meshes()
            obj = merged_object
        else:
            obj = context.active_object

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object")
            return {'CANCELLED'}

        # Delete existing cameras
        delete_all_cameras()
            
        # Create cameras setup with appropriate collection based on keep_cameras setting
        cameras = create_camera_setup(
            props.rows, 
            props.cameras_per_row, 
            props.sphere_radius, 
            props.keep_cameras
        )
        
        # Process faces and get total face count
        total_faces = select_visible_faces_multi_cameras(
            obj, 
            cameras, 
            props.precision_mode,
            props.experimental,
            props.sampling_ratio,
            props.flatness_angle
        )

        if props.delete_select_mode == 'DELETE':
            delete_invisible_faces()
        
        # Merge by distance if option is checked
        if props.merge_by_distance:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.remove_doubles(threshold=0.0001)
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Count remaining faces
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        visible_faces = len(obj.data.polygons)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Only delete cameras if we're not keeping them
        if not props.keep_cameras:
            delete_all_cameras()
            
        # Report detailed statistics
        removal_percent = ((total_faces - visible_faces) / total_faces * 100) if total_faces > 0 else 0
        self.report({'INFO'}, f"Found {visible_faces}/{total_faces} visible faces ({removal_percent:.1f}% removed) using {len(cameras)} cameras")
        
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
        
        # Merge options section (new)
        col = box.column()
        col.prop(props, "merge_meshes")
        col.prop(props, "merge_by_distance")
        col.separator()

        # Rows section
        col = box.column()
        col.label(text="Number of vertical camera splines")
        col.prop(props, "rows")
        col.separator()

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
        
        # Camera visibility option
        col = box.column()
        col.prop(props, "keep_cameras")
        col.separator()

        # Experimental option
        col = box.column()
        col.prop(props, "experimental")
        
        # Experimental settings (conditionally shown)
        if props.experimental:
            col = box.column()
            col.prop(props, "sampling_ratio")
            col.label(text="Percentage of faces to check")
            col.separator()

            col = box.column()
            col.prop(props, "flatness_angle")
            col.label(text="Angle threshold for similar faces")
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