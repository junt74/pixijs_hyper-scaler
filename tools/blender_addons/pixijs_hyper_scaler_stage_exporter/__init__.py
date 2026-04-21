bl_info = {
    "name": "PixiJS Hyper Scaler Stage Exporter",
    "author": "OpenAI Codex",
    "version": (0, 7, 1),
    "blender": (4, 0, 0),
    "location": "File > Export > PixiJS Hyper Scaler Stage (.json)",
    "description": "Export stage.json v1 for PixiJS Hyper Scaler",
    "category": "Import-Export",
}

import json
import math
import os
from datetime import datetime, timezone

import bpy
import gpu
from mathutils import Matrix, Vector
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper
from gpu_extras.batch import batch_for_shader


FORMAT_VERSION = 1
RESERVED_TRIGGER_KEYS = {"event", "once", "name"}
RESERVED_SPRITE_KEYS = {"variant", "route", "name"}
MAX_ARRAY_EXPORT_COPIES = 4096
SPRITE_ARRAY_PREVIEW_HANDLER = None


def sanitize_id(value: str) -> str:
    text = value.strip().lower().replace(" ", "_")
    chars = []
    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            chars.append(char)
    return "".join(chars) or "unnamed"


def engine_vec3(world_location):
    return {
        "x": round(float(world_location.x), 6),
        "y": round(float(world_location.z), 6),
        "z": round(float(world_location.y), 6),
    }


def engine_rotation(world_euler):
    return {
        "yaw": round(math.degrees(float(world_euler.z)), 6),
        "pitch": round(math.degrees(float(world_euler.x)), 6),
        "roll": round(math.degrees(float(world_euler.y)), 6),
    }


def custom_properties(obj, reserved_keys):
    params = {}
    for key in obj.keys():
        if key.startswith("_") or key in reserved_keys:
            continue
        value = obj[key]
        if isinstance(value, (str, int, float, bool)):
            params[key] = value
    return params


def custom_properties_from_id(data_block, reserved_keys):
    params = {}
    if data_block is None or not hasattr(data_block, "keys"):
        return params

    for key in data_block.keys():
        if key.startswith("_") or key in reserved_keys:
            continue
        value = data_block[key]
        if isinstance(value, (str, int, float, bool)):
            params[key] = value

    return params


def merged_custom_properties(obj, reserved_keys):
    params = custom_properties_from_id(getattr(obj, "data", None), reserved_keys)
    params.update(custom_properties_from_id(obj, reserved_keys))
    return params


def get_string_property(obj, key):
    typed_attr = f"pixijs_hs_trigger_{key}"
    if hasattr(obj, typed_attr):
        typed_value = getattr(obj, typed_attr)
        if isinstance(typed_value, str) and typed_value:
            return typed_value

    value = obj.get(key)
    if isinstance(value, str) and value:
        return value

    data_block = getattr(obj, "data", None)
    if data_block is None:
        return None

    value = data_block.get(key)
    if isinstance(value, str) and value:
        return value

    return None


def get_bool_property(obj, key):
    typed_attr = f"pixijs_hs_trigger_{key}"
    if hasattr(obj, typed_attr):
        typed_value = getattr(obj, typed_attr)
        if isinstance(typed_value, bool):
            return typed_value

    value = obj.get(key)
    if isinstance(value, bool):
        return value

    data_block = getattr(obj, "data", None)
    if data_block is None:
        return None

    value = data_block.get(key)
    if isinstance(value, bool):
        return value

    return None


def trigger_params(obj, errors):
    params_json = getattr(obj, "pixijs_hs_trigger_params_json", "")
    if isinstance(params_json, str) and params_json.strip():
        try:
            parsed = json.loads(params_json)
        except json.JSONDecodeError as exc:
            errors.append(f'Trigger "{object_name_path(obj)}" has invalid Trigger Params JSON: {exc.msg}')
            return {}

        if not isinstance(parsed, dict):
            errors.append(f'Trigger "{object_name_path(obj)}" Trigger Params JSON must be an object')
            return {}

        params = {}
        for key, value in parsed.items():
            if not isinstance(key, str):
                errors.append(f'Trigger "{object_name_path(obj)}" has a non-string params key')
                continue
            if key.startswith("_") or key in RESERVED_TRIGGER_KEYS:
                continue
            if isinstance(value, (str, int, float, bool)):
                params[key] = value
            else:
                errors.append(
                    f'Trigger "{object_name_path(obj)}" param "{key}" must be string/number/boolean'
                )
        return params

    return merged_custom_properties(obj, RESERVED_TRIGGER_KEYS)


def object_name_path(obj):
    names = []
    current = obj
    while current is not None:
        names.append(current.name)
        current = current.parent
    return "/".join(reversed(names))


def get_collection(scene, name):
    return scene.collection.children.get(name)


def is_object_in_collection(obj, collection):
    if collection is None:
        return False
    return any(linked_collection == collection for linked_collection in obj.users_collection)


def is_object_in_child_collection(obj, root_collection):
    if root_collection is None:
        return False
    child_names = {collection.name for collection in root_collection.children}
    return any(linked_collection.name in child_names for linked_collection in obj.users_collection)


def tag_redraw_view3d(_self=None, _context=None):
    if bpy.context.window_manager is None:
        return
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def world_transform(obj):
    location, rotation, _scale = obj.matrix_world.decompose()
    return location, rotation.to_euler("XYZ")


def local_bounding_box_size(obj):
    if not obj.bound_box:
        return Vector((0.0, 0.0, 0.0))

    corners = [Vector(corner) for corner in obj.bound_box]
    min_corner = Vector((
        min(corner.x for corner in corners),
        min(corner.y for corner in corners),
        min(corner.z for corner in corners),
    ))
    max_corner = Vector((
        max(corner.x for corner in corners),
        max(corner.y for corner in corners),
        max(corner.z for corner in corners),
    ))
    return max_corner - min_corner


def object_local_offset_matrix(obj, array_modifier):
    step = Vector((0.0, 0.0, 0.0))

    if array_modifier.use_relative_offset:
        relative = Vector(array_modifier.relative_offset_displace)
        bounds = local_bounding_box_size(obj)
        step += Vector((
            bounds.x * relative.x,
            bounds.y * relative.y,
            bounds.z * relative.z,
        ))

    if array_modifier.use_constant_offset:
        step += Vector(array_modifier.constant_offset_displace)

    return Matrix.Translation(step)


def object_offset_step_matrix(array_modifier):
    if not array_modifier.use_object_offset or array_modifier.offset_object is None:
        return Matrix.Identity(4)

    offset_object = array_modifier.offset_object
    base_object = array_modifier.id_data

    return base_object.matrix_world.inverted() @ offset_object.matrix_world


def has_any_modifier(obj):
    return len(obj.modifiers) > 0


def expand_array_matrices(obj, errors):
    transforms = [obj.matrix_world.copy()]

    for modifier in obj.modifiers:
        if modifier.type != "ARRAY":
            continue

        fit_type = getattr(modifier, "fit_type", "FIXED_COUNT")
        if fit_type != "FIXED_COUNT":
            errors.append(
                f'Sprite "{object_name_path(obj)}" uses unsupported Array fit type "{fit_type}"'
            )
            return []

        count = max(1, int(modifier.count))
        if count == 1:
            continue

        local_step = object_local_offset_matrix(obj, modifier)
        object_step = object_offset_step_matrix(modifier)
        step_matrix = local_step @ object_step
        expanded = []

        for base_matrix in transforms:
            current = Matrix.Identity(4)
            for index in range(count):
                if index > 0:
                    current = current @ step_matrix
                expanded.append(base_matrix @ current)
                if len(expanded) > MAX_ARRAY_EXPORT_COPIES:
                    errors.append(
                        f'Sprite "{object_name_path(obj)}" expands beyond {MAX_ARRAY_EXPORT_COPIES} copies'
                    )
                    return []

        transforms = expanded

    return transforms


def connected_vertex_groups(mesh):
    adjacency = {vertex.index: set() for vertex in mesh.vertices}
    for edge in mesh.edges:
        adjacency[edge.vertices[0]].add(edge.vertices[1])
        adjacency[edge.vertices[1]].add(edge.vertices[0])

    groups = []
    remaining = set(adjacency.keys())

    while remaining:
        seed = remaining.pop()
        stack = [seed]
        group = {seed}

        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    group.add(neighbor)
                    stack.append(neighbor)

        groups.append(group)

    return groups


def component_center(mesh, vertex_indices):
    vertices = [mesh.vertices[index].co for index in vertex_indices]
    min_corner = Vector((
        min(vertex.x for vertex in vertices),
        min(vertex.y for vertex in vertices),
        min(vertex.z for vertex in vertices),
    ))
    max_corner = Vector((
        max(vertex.x for vertex in vertices),
        max(vertex.y for vertex in vertices),
        max(vertex.z for vertex in vertices),
    ))
    return (min_corner + max_corner) * 0.5


def evaluated_array_sprite_transforms(obj, depsgraph, errors):
    evaluated_obj = obj.evaluated_get(depsgraph)
    temp_mesh = None

    try:
        temp_mesh = evaluated_obj.to_mesh()
        if temp_mesh is None or len(temp_mesh.vertices) == 0:
            return []

        groups = connected_vertex_groups(temp_mesh)
        if len(groups) <= 1:
            return []

        world_rotation = evaluated_obj.matrix_world.decompose()[1].to_euler("XYZ")
        transforms = []

        for group in groups:
            local_center = component_center(temp_mesh, group)
            world_center = evaluated_obj.matrix_world @ local_center
            transforms.append(
                (
                    world_center,
                    world_rotation,
                )
            )
            if len(transforms) > MAX_ARRAY_EXPORT_COPIES:
                errors.append(
                    f'Sprite "{object_name_path(obj)}" expands beyond {MAX_ARRAY_EXPORT_COPIES} copies'
                )
                return []

        return transforms
    finally:
        if temp_mesh is not None:
            evaluated_obj.to_mesh_clear()


def custom_sprite_array_transforms(obj):
    count_x = max(1, int(getattr(obj, "pixijs_hs_sprite_array_count_x", 1)))
    count_y = max(1, int(getattr(obj, "pixijs_hs_sprite_array_count_y", 1)))
    count_z = max(1, int(getattr(obj, "pixijs_hs_sprite_array_count_z", 1)))
    local_step = Vector((
        float(getattr(obj, "pixijs_hs_sprite_array_step_x", 0.0)),
        float(getattr(obj, "pixijs_hs_sprite_array_step_y", 0.0)),
        float(getattr(obj, "pixijs_hs_sprite_array_step_z", 0.0)),
    ))
    world_rotation = obj.matrix_world.decompose()[1].to_euler("XYZ")

    transforms = []
    for index_x in range(count_x):
        for index_y in range(count_y):
            for index_z in range(count_z):
                local_offset = Vector((
                    local_step.x * index_x,
                    local_step.y * index_y,
                    local_step.z * index_z,
                ))
                world_location = obj.matrix_world @ local_offset
                transforms.append((world_location, world_rotation))
                if len(transforms) > MAX_ARRAY_EXPORT_COPIES:
                    return transforms[:MAX_ARRAY_EXPORT_COPIES]

    return transforms


def extend_crosshair_coords(coords, position, marker_size):
    coords.extend([
        position + Vector((-marker_size, 0.0, 0.0)),
        position + Vector((marker_size, 0.0, 0.0)),
        position + Vector((0.0, -marker_size, 0.0)),
        position + Vector((0.0, marker_size, 0.0)),
        position + Vector((0.0, 0.0, -marker_size)),
        position + Vector((0.0, 0.0, marker_size)),
    ])


def draw_sprite_array_preview():
    context = bpy.context
    if context is None:
        return

    sprites_root = get_collection(context.scene, "Sprites")
    if sprites_root is None:
        return

    marker_size = 0.15
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    active_coords = []
    inactive_coords = []
    active_object = context.active_object
    depsgraph = context.evaluated_depsgraph_get()
    preview_errors = []

    for child_collection in sprites_root.children:
        for obj in child_collection.objects:
            placements = []
            if obj.type == "CURVE":
                if getattr(obj, "pixijs_hs_curve_sprite_enabled", False):
                    placements = sample_curve_sprite_transforms(obj, depsgraph, preview_errors)
            elif getattr(obj, "pixijs_hs_sprite_array_enabled", False):
                placements = custom_sprite_array_transforms(obj)

            if not placements:
                continue

            target_coords = active_coords if obj == active_object else inactive_coords
            for position, _rotation in placements:
                extend_crosshair_coords(target_coords, position, marker_size)

    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(2.0)
    if inactive_coords:
        inactive_batch = batch_for_shader(shader, "LINES", {"pos": inactive_coords})
        shader.bind()
        shader.uniform_float("color", (0.45, 0.65, 0.75, 0.45))
        inactive_batch.draw(shader)
    if active_coords:
        active_batch = batch_for_shader(shader, "LINES", {"pos": active_coords})
        shader.bind()
        shader.uniform_float("color", (0.35, 0.95, 1.0, 0.9))
        active_batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


def connected_vertex_components(mesh):
    adjacency = {vertex.index: set() for vertex in mesh.vertices}
    for edge in mesh.edges:
        adjacency[edge.vertices[0]].add(edge.vertices[1])
        adjacency[edge.vertices[1]].add(edge.vertices[0])

    components = []
    remaining = set(adjacency.keys())

    while remaining:
        seed = remaining.pop()
        stack = [seed]
        component = {seed}

        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)

        components.append(component)

    return adjacency, components


def ordered_component_vertices(mesh, adjacency, component):
    component_adjacency = {
        index: [neighbor for neighbor in adjacency[index] if neighbor in component]
        for index in component
    }
    endpoints = [index for index, neighbors in component_adjacency.items() if len(neighbors) <= 1]
    is_cyclic = len(endpoints) == 0
    start = endpoints[0] if endpoints else min(component)

    ordered_indices = [start]
    visited = {start}
    previous = None
    current = start

    while True:
        neighbors = [neighbor for neighbor in component_adjacency[current] if neighbor != previous]
        next_index = next((neighbor for neighbor in neighbors if neighbor not in visited), None)

        if next_index is None:
            if is_cyclic and len(ordered_indices) == len(component):
                ordered_indices.append(start)
            break

        ordered_indices.append(next_index)
        visited.add(next_index)
        previous = current
        current = next_index

    return [mesh.vertices[index].co.copy() for index in ordered_indices], is_cyclic


def sample_polyline_point(points, distance):
    if not points:
        return None
    if len(points) == 1:
        return points[0].copy()

    remaining = max(0.0, distance)
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        segment = end - start
        segment_length = segment.length
        if segment_length <= 1e-6:
            continue
        if remaining <= segment_length:
            return start + segment * (remaining / segment_length)
        remaining -= segment_length

    return points[-1].copy()


def polyline_total_length(points):
    total_length = 0.0
    for index in range(len(points) - 1):
        total_length += (points[index + 1] - points[index]).length
    return total_length


def sample_polyline_positions(points, spacing, start_offset, end_inset, is_cyclic, include_end_point):
    if len(points) < 2:
        return []

    total_length = polyline_total_length(points)
    if total_length <= 1e-6:
        return []

    end_distance = total_length - end_inset
    if end_distance < start_offset:
        return []

    sampled_points = []
    sample_distance = start_offset
    while sample_distance <= end_distance + 1e-6:
        if is_cyclic and sample_distance >= end_distance - 1e-6:
            break

        sample_point = sample_polyline_point(points, sample_distance)
        if sample_point is None:
            break
        sampled_points.append(sample_point)
        sample_distance += spacing

    if include_end_point and not is_cyclic:
        end_point = sample_polyline_point(points, end_distance)
        if end_point is not None:
            if not sampled_points or (sampled_points[-1] - end_point).length > 1e-6:
                sampled_points.append(end_point)

    return sampled_points


def sample_curve_sprite_transforms(obj, depsgraph, errors):
    if not getattr(obj, "pixijs_hs_curve_sprite_enabled", False):
        return []

    spacing = float(getattr(obj, "pixijs_hs_curve_sprite_spacing", 1.0))
    if spacing <= 0:
        errors.append(f'Curve sprite "{object_name_path(obj)}" has non-positive spacing')
        return []

    start_offset = max(0.0, float(getattr(obj, "pixijs_hs_curve_sprite_start_offset", 0.0)))
    end_inset = max(0.0, float(getattr(obj, "pixijs_hs_curve_sprite_end_inset", 0.0)))
    local_offset = Vector((
        float(getattr(obj, "pixijs_hs_curve_sprite_offset_x", 0.0)),
        float(getattr(obj, "pixijs_hs_curve_sprite_offset_y", 0.0)),
        float(getattr(obj, "pixijs_hs_curve_sprite_offset_z", 0.0)),
    ))

    evaluated_obj = obj.evaluated_get(depsgraph)
    temp_mesh = None

    try:
        temp_mesh = evaluated_obj.to_mesh()
        if temp_mesh is None or len(temp_mesh.vertices) == 0:
            return []

        adjacency, components = connected_vertex_components(temp_mesh)
        transforms = []

        for component in components:
            points, is_cyclic = ordered_component_vertices(temp_mesh, adjacency, component)
            sampled_points = sample_polyline_positions(
                points,
                spacing,
                start_offset,
                end_inset,
                is_cyclic,
                False,
            )

            for sample_point in sampled_points:
                world_point = evaluated_obj.matrix_world @ (sample_point + local_offset)
                transforms.append((world_point, None))
                if len(transforms) > MAX_ARRAY_EXPORT_COPIES:
                    errors.append(
                        f'Curve sprite "{object_name_path(obj)}" expands beyond {MAX_ARRAY_EXPORT_COPIES} copies'
                    )
                    return []

        return transforms
    finally:
        if temp_mesh is not None:
            evaluated_obj.to_mesh_clear()


def sample_waypoint_curve_positions(obj, depsgraph, errors):
    spacing = float(getattr(obj, "pixijs_hs_waypoint_curve_spacing", 1.0))
    if spacing <= 0:
        errors.append(f'Waypoint curve "{object_name_path(obj)}" has non-positive spacing')
        return []

    start_offset = max(0.0, float(getattr(obj, "pixijs_hs_waypoint_curve_start_offset", 0.0)))
    end_inset = max(0.0, float(getattr(obj, "pixijs_hs_waypoint_curve_end_inset", 0.0)))

    evaluated_obj = obj.evaluated_get(depsgraph)
    temp_mesh = None

    try:
        temp_mesh = evaluated_obj.to_mesh()
        if temp_mesh is None or len(temp_mesh.vertices) == 0:
            return []

        adjacency, components = connected_vertex_components(temp_mesh)
        if len(components) != 1:
            errors.append(
                f'Waypoint curve "{object_name_path(obj)}" must contain exactly one connected spline'
            )
            return []

        points, is_cyclic = ordered_component_vertices(temp_mesh, adjacency, components[0])
        if is_cyclic:
            errors.append(
                f'Waypoint curve "{object_name_path(obj)}" must be open (cyclic curves are unsupported)'
            )
            return []

        sampled_points = sample_polyline_positions(
            points,
            spacing,
            start_offset,
            end_inset,
            is_cyclic,
            True,
        )

        return [evaluated_obj.matrix_world @ sample_point for sample_point in sampled_points]
    finally:
        if temp_mesh is not None:
            evaluated_obj.to_mesh_clear()


def estimate_waypoint_curve_sample_count(obj):
    context = bpy.context
    if context is None:
        return None

    depsgraph = context.evaluated_depsgraph_get()
    preview_errors = []
    positions = sample_waypoint_curve_positions(obj, depsgraph, preview_errors)
    if preview_errors:
        return None
    return len(positions)


def export_waypoints(scene, errors):
    collection = get_collection(scene, "Waypoints")
    if collection is None:
        errors.append('Missing required collection "Waypoints"')
        return []

    objects = sorted(collection.objects, key=lambda obj: obj.name)
    depsgraph = bpy.context.evaluated_depsgraph_get()

    result = []
    for obj in objects:
        if obj.type == "CURVE":
            positions = sample_waypoint_curve_positions(obj, depsgraph, errors)
            for sample_index, location in enumerate(positions):
                result.append(
                    {
                        "id": f"wp_{len(result):03d}_{sanitize_id(obj.name)}_{sample_index:03d}",
                        "position": engine_vec3(location),
                    }
                )
            continue

        location, _rotation = world_transform(obj)
        result.append(
            {
                "id": f"wp_{len(result):03d}_{sanitize_id(obj.name)}",
                "position": engine_vec3(location),
            }
        )

    if len(result) < 2:
        errors.append('"Waypoints" must export at least 2 points')
    return result


def export_colliders(scene, errors):
    collection = get_collection(scene, "Colliders")
    if collection is None:
        return []

    result = []
    for obj in sorted(collection.objects, key=lambda item: item.name):
        location, rotation = world_transform(obj)
        half_extents = engine_vec3(obj.dimensions / 2.0)
        if half_extents["x"] <= 0 or half_extents["y"] <= 0 or half_extents["z"] <= 0:
            errors.append(f'Collider "{object_name_path(obj)}" has a non-positive size')
            continue

        collider = {
            "id": f"col_{sanitize_id(obj.name)}",
            "name": obj.name,
            "type": "box",
            "position": engine_vec3(location),
            "rotation": engine_rotation(rotation),
            "halfExtents": half_extents,
        }

        layer = obj.get("layer")
        if isinstance(layer, str) and layer:
            collider["layer"] = layer

        result.append(collider)
    return result


def export_sprites(scene, errors):
    root = get_collection(scene, "Sprites")
    if root is None:
        return [], []

    depsgraph = bpy.context.evaluated_depsgraph_get()
    result = []
    diagnostics = []
    for child_collection in sorted(root.children, key=lambda collection: collection.name):
        sprite_type = child_collection.name
        for obj in sorted(child_collection.objects, key=lambda item: item.name):
            params = merged_custom_properties(obj, RESERVED_SPRITE_KEYS)
            placements = []
            mode = "single"
            evaluated_parts = 0
            manual_count = 0
            curve_count = 0
            custom_array_count = 0

            if obj.type != "CURVE" and getattr(obj, "pixijs_hs_sprite_array_enabled", False):
                placements = custom_sprite_array_transforms(obj)
                custom_array_count = len(placements)
                if placements:
                    mode = "custom_array"

            if not placements and obj.type == "CURVE":
                placements = sample_curve_sprite_transforms(obj, depsgraph, errors)
                curve_count = len(placements)
                if placements:
                    mode = "curve_sprite"

            if not placements and obj.type == "MESH" and has_any_modifier(obj):
                placements = evaluated_array_sprite_transforms(obj, depsgraph, errors)
                evaluated_parts = len(placements)
                if placements:
                    mode = "evaluated_mesh"

            if not placements:
                transforms = expand_array_matrices(obj, errors)
                if not transforms:
                    continue
                manual_count = len(transforms)
                if manual_count > 1:
                    mode = "manual_array"
                placements = [
                    (matrix_world.decompose()[0], matrix_world.decompose()[1].to_euler("XYZ"))
                    for matrix_world in transforms
                ]

            diagnostics.append({
                "object": obj.name,
                "type": sprite_type,
                "mode": mode,
                "arrayModifierCount": sum(1 for modifier in obj.modifiers if modifier.type == "ARRAY"),
                "modifierCount": len(obj.modifiers),
                "modifierTypes": [modifier.type for modifier in obj.modifiers],
                "evaluatedPartCount": evaluated_parts,
                "customArrayCount": custom_array_count,
                "curvePlacementCount": curve_count,
                "exportedPlacementCount": len(placements),
                "manualPlacementCount": manual_count,
            })

            needs_index_suffix = len(placements) > 1

            for index, (location, rotation) in enumerate(placements):
                sprite_id = f"spr_{sanitize_id(sprite_type)}_{sanitize_id(obj.name)}"
                sprite_name = obj.name

                if needs_index_suffix:
                    sprite_id = f"{sprite_id}_{index:03d}"
                    sprite_name = f"{sprite_name}.{index:03d}"

                sprite = {
                    "id": sprite_id,
                    "name": sprite_name,
                    "type": sprite_type,
                    "position": engine_vec3(location),
                    "yaw": round(math.degrees(float(rotation.z)), 6) if rotation is not None else 0.0,
                }

                if params:
                    sprite["params"] = params

                result.append(sprite)

    if root.children and not result:
        errors.append('"Sprites" has child collections but no objects to export')

    return result, diagnostics


def export_triggers(scene, errors):
    collection = get_collection(scene, "Triggers")
    if collection is None:
        return []

    result = []
    for obj in sorted(collection.objects, key=lambda item: item.name):
        event_name = get_string_property(obj, "event")
        if event_name is None:
            errors.append(f'Trigger "{object_name_path(obj)}" is missing string custom property "event"')
            continue

        location, rotation = world_transform(obj)
        half_extents = engine_vec3(obj.dimensions / 2.0)
        if half_extents["x"] <= 0 or half_extents["y"] <= 0 or half_extents["z"] <= 0:
            errors.append(f'Trigger "{object_name_path(obj)}" has a non-positive size')
            continue

        trigger = {
            "id": f"trg_{sanitize_id(obj.name)}",
            "name": obj.name,
            "event": event_name,
            "once": bool(get_bool_property(obj, "once")),
            "position": engine_vec3(location),
            "rotation": engine_rotation(rotation),
            "halfExtents": half_extents,
        }

        params = trigger_params(obj, errors)
        if params:
            trigger["params"] = params

        result.append(trigger)
    return result


def build_stage_data(context, include_sprite_diagnostics=False):
    scene = context.scene
    errors = []

    stage_id = scene.pixijs_hs_stage_id or scene.get("stage_id") or sanitize_id(scene.name)
    source_scene = os.path.basename(bpy.data.filepath) if bpy.data.filepath else f"{scene.name}.blend"

    sprites, sprite_diagnostics = export_sprites(scene, errors)

    source = {
        "dcc": "Blender",
        "scene": source_scene,
        "exporterVersion": "0.7.1",
    }
    if include_sprite_diagnostics:
        source["spriteExportDiagnostics"] = sprite_diagnostics

    data = {
        "formatVersion": FORMAT_VERSION,
        "stageId": stage_id,
        "name": scene.pixijs_hs_stage_name or scene.get("stage_name") or scene.name,
        "source": source,
        "meta": {
            "exportedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
        "waypoints": export_waypoints(scene, errors),
        "colliders": export_colliders(scene, errors),
        "sprites": sprites,
        "triggers": export_triggers(scene, errors),
    }

    return data, errors


class EXPORT_SCENE_OT_pixijs_hyper_scaler_stage(Operator, ExportHelper):
    bl_idname = "export_scene.pixijs_hyper_scaler_stage"
    bl_label = "Export PixiJS Hyper Scaler Stage"
    bl_options = {"PRESET"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})
    pretty_print: BoolProperty(
        name="Pretty Print",
        description="Write formatted JSON for easier diffing and debugging",
        default=True,
    )
    include_sprite_diagnostics: BoolProperty(
        name="Include Sprite Diagnostics",
        description="Write sprite export diagnostics under source.spriteExportDiagnostics",
        default=False,
    )

    def execute(self, context):
        stage_data, errors = build_stage_data(
            context,
            include_sprite_diagnostics=self.include_sprite_diagnostics,
        )
        if errors:
            for error in errors:
                self.report({"ERROR"}, error)
            return {"CANCELLED"}

        indent = 2 if self.pretty_print else None
        with open(self.filepath, "w", encoding="utf-8") as file:
            json.dump(stage_data, file, ensure_ascii=False, indent=indent)
            file.write("\n")

        self.report(
            {"INFO"},
            (
                f'Exported stage data to {self.filepath} '
                f'({len(stage_data["sprites"])} sprites, {len(stage_data["waypoints"])} waypoints, '
                f'{len(stage_data["colliders"])} colliders, {len(stage_data["triggers"])} triggers)'
            ),
        )
        return {"FINISHED"}


class VIEW3D_PT_pixijs_hyper_scaler_stage_export(Panel):
    bl_label = "PixiJS Hyper Scaler"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HyperScaler"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "pixijs_hs_stage_id", text="Stage ID")
        layout.prop(scene, "pixijs_hs_stage_name", text="Stage Name")
        layout.prop(scene, "pixijs_hs_include_sprite_diagnostics", text="Sprite Diagnostics")
        layout.separator()
        layout.label(text="Required collections:")
        layout.label(text="Waypoints")
        layout.label(text="Optional: Colliders, Sprites, Triggers")
        operator = layout.operator(EXPORT_SCENE_OT_pixijs_hyper_scaler_stage.bl_idname, icon="EXPORT")
        operator.include_sprite_diagnostics = scene.pixijs_hs_include_sprite_diagnostics


class VIEW3D_PT_pixijs_hyper_scaler_trigger(Panel):
    bl_label = "Trigger"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HyperScaler"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None:
            return False
        return is_object_in_collection(obj, get_collection(context.scene, "Triggers"))

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        layout.prop(obj, "pixijs_hs_trigger_event", text="Event")
        layout.prop(obj, "pixijs_hs_trigger_once", text="Once")
        layout.prop(obj, "pixijs_hs_trigger_params_json", text="Params JSON")
        layout.label(text="Writes object-side trigger fields")


class VIEW3D_PT_pixijs_hyper_scaler_sprite_array(Panel):
    bl_label = "Sprite Array"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HyperScaler"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type == "CURVE":
            return False
        sprites_root = get_collection(context.scene, "Sprites")
        return is_object_in_child_collection(obj, sprites_root)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        layout.prop(obj, "pixijs_hs_sprite_array_enabled", text="Enabled")
        column = layout.column()
        column.enabled = obj.pixijs_hs_sprite_array_enabled
        column.label(text="Grid Count")
        column.prop(obj, "pixijs_hs_sprite_array_count_x", text="X")
        column.prop(obj, "pixijs_hs_sprite_array_count_y", text="Y")
        column.prop(obj, "pixijs_hs_sprite_array_count_z", text="Z")
        column.label(text="Grid Step")
        column.prop(obj, "pixijs_hs_sprite_array_step_x", text="X")
        column.prop(obj, "pixijs_hs_sprite_array_step_y", text="Y")
        column.prop(obj, "pixijs_hs_sprite_array_step_z", text="Z")
        column.label(text="Preview stays visible while unselected")


class VIEW3D_PT_pixijs_hyper_scaler_curve_sprite(Panel):
    bl_label = "Curve Sprite"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HyperScaler"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "CURVE"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        sprites_root = get_collection(context.scene, "Sprites")
        is_sprite_curve = is_object_in_child_collection(obj, sprites_root)

        if not is_sprite_curve:
            layout.label(text='Place this curve under "Sprites/<type>/" to export', icon="INFO")

        layout.prop(obj, "pixijs_hs_curve_sprite_enabled", text="Enabled")
        column = layout.column()
        column.enabled = obj.pixijs_hs_curve_sprite_enabled
        column.prop(obj, "pixijs_hs_curve_sprite_spacing", text="Spacing")
        column.prop(obj, "pixijs_hs_curve_sprite_start_offset", text="Start Offset")
        column.prop(obj, "pixijs_hs_curve_sprite_end_inset", text="End Inset")
        column.label(text="Local Offset")
        column.prop(obj, "pixijs_hs_curve_sprite_offset_x", text="X")
        column.prop(obj, "pixijs_hs_curve_sprite_offset_y", text="Y")
        column.prop(obj, "pixijs_hs_curve_sprite_offset_z", text="Z")
        column.label(text="Yaw is exported as 0 for billboard sprites")
        column.label(text="Preview stays visible while unselected")


class VIEW3D_PT_pixijs_hyper_scaler_waypoint_curve(Panel):
    bl_label = "Waypoint Curve"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HyperScaler"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != "CURVE":
            return False
        return is_object_in_collection(obj, get_collection(context.scene, "Waypoints"))

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        layout.label(text='Curve is baked into ordered waypoints', icon="CURVE_DATA")
        column = layout.column()
        column.prop(obj, "pixijs_hs_waypoint_curve_spacing", text="Sampling Step")
        column.prop(obj, "pixijs_hs_waypoint_curve_start_offset", text="Start Offset")
        column.prop(obj, "pixijs_hs_waypoint_curve_end_inset", text="End Inset")
        column.label(text="Smaller step = denser waypoint samples")
        sample_count = estimate_waypoint_curve_sample_count(obj)
        if sample_count is not None:
            column.label(text=f"Estimated exported waypoints: {sample_count}")
        column.label(text="Exports an open curve as a waypoint rail")


def menu_func_export(self, _context):
    self.layout.operator(
        EXPORT_SCENE_OT_pixijs_hyper_scaler_stage.bl_idname,
        text="PixiJS Hyper Scaler Stage (.json)",
    )


CLASSES = (
    EXPORT_SCENE_OT_pixijs_hyper_scaler_stage,
    VIEW3D_PT_pixijs_hyper_scaler_stage_export,
    VIEW3D_PT_pixijs_hyper_scaler_trigger,
    VIEW3D_PT_pixijs_hyper_scaler_sprite_array,
    VIEW3D_PT_pixijs_hyper_scaler_curve_sprite,
    VIEW3D_PT_pixijs_hyper_scaler_waypoint_curve,
)


def register():
    bpy.types.Scene.pixijs_hs_stage_id = StringProperty(
        name="Stage ID",
        description="Logical stage identifier written to stage.json",
        default="",
    )
    bpy.types.Scene.pixijs_hs_stage_name = StringProperty(
        name="Stage Name",
        description="Display name written to stage.json",
        default="",
    )
    bpy.types.Scene.pixijs_hs_include_sprite_diagnostics = BoolProperty(
        name="Include Sprite Diagnostics",
        description="Write sprite export diagnostics under source.spriteExportDiagnostics",
        default=False,
    )
    bpy.types.Object.pixijs_hs_trigger_event = StringProperty(
        name="Trigger Event",
        description="Trigger event name exported as triggers[*].event",
        default="",
    )
    bpy.types.Object.pixijs_hs_trigger_once = BoolProperty(
        name="Trigger Once",
        description="When true, the trigger should fire only once",
        default=False,
    )
    bpy.types.Object.pixijs_hs_trigger_params_json = StringProperty(
        name="Trigger Params JSON",
        description="Optional JSON object exported as triggers[*].params",
        default="",
    )
    bpy.types.Object.pixijs_hs_sprite_array_enabled = BoolProperty(
        name="Sprite Array Enabled",
        description="Export this sprite object as a simple repeated array",
        default=False,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_sprite_array_count_x = bpy.props.IntProperty(
        name="Sprite Array Count X",
        description="How many sprite placements to export on X",
        default=1,
        min=1,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_sprite_array_count_y = bpy.props.IntProperty(
        name="Sprite Array Count Y",
        description="How many sprite placements to export on Y",
        default=1,
        min=1,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_sprite_array_count_z = bpy.props.IntProperty(
        name="Sprite Array Count Z",
        description="How many sprite placements to export on Z",
        default=1,
        min=1,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_sprite_array_step_x = FloatProperty(
        name="Sprite Array Step X",
        description="Local X step between grid elements",
        default=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_sprite_array_step_y = FloatProperty(
        name="Sprite Array Step Y",
        description="Local Y step between grid elements",
        default=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_sprite_array_step_z = FloatProperty(
        name="Sprite Array Step Z",
        description="Local Z step between grid elements",
        default=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_curve_sprite_enabled = BoolProperty(
        name="Curve Sprite Enabled",
        description="Export this curve as evenly spaced sprite placements",
        default=False,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_curve_sprite_spacing = FloatProperty(
        name="Curve Sprite Spacing",
        description="Distance between generated sprite placements",
        default=1.0,
        min=0.001,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_curve_sprite_start_offset = FloatProperty(
        name="Curve Sprite Start Offset",
        description="Distance from the beginning of the curve before placing the first sprite",
        default=0.0,
        min=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_curve_sprite_end_inset = FloatProperty(
        name="Curve Sprite End Inset",
        description="Distance from the end of the curve where placement stops",
        default=0.0,
        min=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_curve_sprite_offset_x = FloatProperty(
        name="Curve Sprite Offset X",
        description="Local X offset applied before export",
        default=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_curve_sprite_offset_y = FloatProperty(
        name="Curve Sprite Offset Y",
        description="Local Y offset applied before export",
        default=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_curve_sprite_offset_z = FloatProperty(
        name="Curve Sprite Offset Z",
        description="Local Z offset applied before export",
        default=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_waypoint_curve_spacing = FloatProperty(
        name="Waypoint Curve Sampling Step",
        description="Distance between baked waypoint samples along the curve; smaller values produce denser rails",
        default=1.0,
        min=0.001,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_waypoint_curve_start_offset = FloatProperty(
        name="Waypoint Curve Start Offset",
        description="Distance from the beginning of the curve before the first waypoint sample",
        default=0.0,
        min=0.0,
        update=tag_redraw_view3d,
    )
    bpy.types.Object.pixijs_hs_waypoint_curve_end_inset = FloatProperty(
        name="Waypoint Curve End Inset",
        description="Distance from the end of the curve where waypoint sampling stops",
        default=0.0,
        min=0.0,
        update=tag_redraw_view3d,
    )
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    global SPRITE_ARRAY_PREVIEW_HANDLER
    if SPRITE_ARRAY_PREVIEW_HANDLER is None:
        SPRITE_ARRAY_PREVIEW_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
            draw_sprite_array_preview,
            (),
            "WINDOW",
            "POST_VIEW",
        )


def unregister():
    global SPRITE_ARRAY_PREVIEW_HANDLER
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    if SPRITE_ARRAY_PREVIEW_HANDLER is not None:
        bpy.types.SpaceView3D.draw_handler_remove(SPRITE_ARRAY_PREVIEW_HANDLER, "WINDOW")
        SPRITE_ARRAY_PREVIEW_HANDLER = None
    del bpy.types.Object.pixijs_hs_sprite_array_step_z
    del bpy.types.Object.pixijs_hs_sprite_array_step_y
    del bpy.types.Object.pixijs_hs_sprite_array_step_x
    del bpy.types.Object.pixijs_hs_sprite_array_count_z
    del bpy.types.Object.pixijs_hs_sprite_array_count_y
    del bpy.types.Object.pixijs_hs_sprite_array_count_x
    del bpy.types.Object.pixijs_hs_sprite_array_enabled
    del bpy.types.Object.pixijs_hs_curve_sprite_offset_z
    del bpy.types.Object.pixijs_hs_curve_sprite_offset_y
    del bpy.types.Object.pixijs_hs_curve_sprite_offset_x
    del bpy.types.Object.pixijs_hs_curve_sprite_end_inset
    del bpy.types.Object.pixijs_hs_curve_sprite_start_offset
    del bpy.types.Object.pixijs_hs_curve_sprite_spacing
    del bpy.types.Object.pixijs_hs_curve_sprite_enabled
    del bpy.types.Object.pixijs_hs_waypoint_curve_end_inset
    del bpy.types.Object.pixijs_hs_waypoint_curve_start_offset
    del bpy.types.Object.pixijs_hs_waypoint_curve_spacing
    del bpy.types.Object.pixijs_hs_trigger_params_json
    del bpy.types.Object.pixijs_hs_trigger_once
    del bpy.types.Object.pixijs_hs_trigger_event
    del bpy.types.Scene.pixijs_hs_include_sprite_diagnostics
    del bpy.types.Scene.pixijs_hs_stage_name
    del bpy.types.Scene.pixijs_hs_stage_id


if __name__ == "__main__":
    register()
