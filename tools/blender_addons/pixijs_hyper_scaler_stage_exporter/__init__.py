bl_info = {
    "name": "PixiJS Hyper Scaler Stage Exporter",
    "author": "OpenAI Codex",
    "version": (0, 1, 0),
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
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper


FORMAT_VERSION = 1
RESERVED_TRIGGER_KEYS = {"event", "name"}
RESERVED_SPRITE_KEYS = {"variant", "route", "name"}


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


def object_name_path(obj):
    names = []
    current = obj
    while current is not None:
        names.append(current.name)
        current = current.parent
    return "/".join(reversed(names))


def get_collection(scene, name):
    return scene.collection.children.get(name)


def world_transform(obj):
    location, rotation, _scale = obj.matrix_world.decompose()
    return location, rotation.to_euler("XYZ")


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
        return []

    result = []
    for child_collection in sorted(root.children, key=lambda collection: collection.name):
        sprite_type = child_collection.name
        for obj in sorted(child_collection.objects, key=lambda item: item.name):
            location, rotation = world_transform(obj)
            sprite = {
                "id": f"spr_{sanitize_id(sprite_type)}_{sanitize_id(obj.name)}",
                "name": obj.name,
                "type": sprite_type,
                "position": engine_vec3(location),
                "yaw": round(math.degrees(float(rotation.z)), 6),
            }

            params = custom_properties(obj, RESERVED_SPRITE_KEYS)
            if params:
                sprite["params"] = params

            result.append(sprite)

    if root.children and not result:
        errors.append('"Sprites" has child collections but no objects to export')

    return result


def export_triggers(scene, errors):
    collection = get_collection(scene, "Triggers")
    if collection is None:
        return []

    result = []
    for obj in sorted(collection.objects, key=lambda item: item.name):
        event_name = obj.get("event")
        if not isinstance(event_name, str) or not event_name:
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
            "position": engine_vec3(location),
            "rotation": engine_rotation(rotation),
            "halfExtents": half_extents,
        }

        params = custom_properties(obj, RESERVED_TRIGGER_KEYS)
        if params:
            trigger["params"] = params

        result.append(trigger)
    return result


def build_stage_data(context):
    scene = context.scene
    errors = []

    stage_id = scene.pixijs_hs_stage_id or scene.get("stage_id") or sanitize_id(scene.name)
    source_scene = os.path.basename(bpy.data.filepath) if bpy.data.filepath else f"{scene.name}.blend"

    data = {
        "formatVersion": FORMAT_VERSION,
        "stageId": stage_id,
        "name": scene.pixijs_hs_stage_name or scene.get("stage_name") or scene.name,
        "source": {
            "dcc": "Blender",
            "scene": source_scene,
        },
        "meta": {
            "exportedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
        "waypoints": export_waypoints(scene, errors),
        "colliders": export_colliders(scene, errors),
        "sprites": export_sprites(scene, errors),
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

    def execute(self, context):
        stage_data, errors = build_stage_data(context)
        if errors:
            for error in errors:
                self.report({"ERROR"}, error)
            return {"CANCELLED"}

        indent = 2 if self.pretty_print else None
        with open(self.filepath, "w", encoding="utf-8") as file:
            json.dump(stage_data, file, ensure_ascii=False, indent=indent)
            file.write("\n")

        self.report({"INFO"}, f"Exported stage data to {self.filepath}")
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
        layout.separator()
        layout.label(text="Required collections:")
        layout.label(text="Waypoints")
        layout.label(text="Optional: Colliders, Sprites, Triggers")
        layout.operator(EXPORT_SCENE_OT_pixijs_hyper_scaler_stage.bl_idname, icon="EXPORT")


def menu_func_export(self, _context):
    self.layout.operator(
        EXPORT_SCENE_OT_pixijs_hyper_scaler_stage.bl_idname,
        text="PixiJS Hyper Scaler Stage (.json)",
    )


CLASSES = (
    EXPORT_SCENE_OT_pixijs_hyper_scaler_stage,
    VIEW3D_PT_pixijs_hyper_scaler_stage_export,
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
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.pixijs_hs_stage_name
    del bpy.types.Scene.pixijs_hs_stage_id


if __name__ == "__main__":
    register()
