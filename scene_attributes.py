from blender import run_blender, dump_dict, recover_dict


# You can actually get the start and end frames without starting Blender itself using:
#  https://github.com/dfelinto/blender/blob/master/release/scripts/modules/blend_render_info.py
# Just run `python3 blend_render_info.py blend-file.blend` - it doesn't need any additional libraries.
# However, it's limited to just that information.
def get_scene_attributes(blender, input_file):
    code = f"""
        import bpy

        scene = bpy.context.scene

        attributes = {{
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_step": scene.frame_step,
            "samples": scene.cycles.samples,
            "motion_blur": scene.render.use_motion_blur
        }}

        {dump_dict("attributes")}
    """
    return recover_dict(run_blender(blender, input_file, code, capture_output=True))
