bl_info = {
    "name": "PixiJS Hyper Scaler Stage Exporter",
    "author": "OpenAI Codex",
    "version": (0, 5, 0),
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
from mathutils import Matrix, Vector
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper


FORMAT_VERSION = 1
RESERVED_TRIGGER_KEYS = {"event", "once", "name"}
RESERVED_SPRITE_KEYS = {"variant", "route", "name"}
MAX_ARRAY_EXPORT_COPIES = 4096


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


def export_waypoints(scene, errors):
    collection = get_collection(scene, "Waypoints")
    if collection is None:
        errors.append('Missing required collection "Waypoints"')
        return []

    objects = sorted(collection.objects, key=lambda obj: obj.name)
    if len(objects) < 2:
        errors.append('"Waypoints" must contain at least 2 objects')
        return []

    result = []
    for index, obj in enumerate(objects):
        location, _rotation = world_transform(obj)
        result.append(
            {
                "id": f"wp_{index:03d}_{sanitize_id(obj.name)}",
                "position": engine_vec3(location),
            }
        )
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

            if obj.type == "MESH" and has_any_modifier(obj):
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
                    "yaw": round(math.degrees(float(rotation.z)), 6),
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
        "exporterVersion": "0.5.0",
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


def menu_func_export(self, _context):
    self.layout.operator(
        EXPORT_SCENE_OT_pixijs_hyper_scaler_stage.bl_idname,
        text="PixiJS Hyper Scaler Stage (.json)",
    )


CLASSES = (
    EXPORT_SCENE_OT_pixijs_hyper_scaler_stage,
    VIEW3D_PT_pixijs_hyper_scaler_stage_export,
    VIEW3D_PT_pixijs_hyper_scaler_trigger,
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
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Object.pixijs_hs_trigger_params_json
    del bpy.types.Object.pixijs_hs_trigger_once
    del bpy.types.Object.pixijs_hs_trigger_event
    del bpy.types.Scene.pixijs_hs_include_sprite_diagnostics
    del bpy.types.Scene.pixijs_hs_stage_name
    del bpy.types.Scene.pixijs_hs_stage_id


if __name__ == "__main__":
    register()
