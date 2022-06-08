import json
import subprocess
import textwrap
import re

_START_MARKER = "START>"
_END_MARKER = "<END"
_MATCHER = re.compile(f"{_START_MARKER}(.*){_END_MARKER}")


# You can actually get the start and end frames without starting Blender itself using:
#  https://github.com/dfelinto/blender/blob/master/release/scripts/modules/blend_render_info.py
# Just run `python3 blend_render_info.py blend-file.blend` - it doesn't need any additional libraries.
# However, it's limited to just that information.
def _get_python_expr():
    code = f"""
        import bpy
        import json
        
        scene = bpy.context.scene
                
        attributes = {{
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_step": scene.frame_step,
            "samples": scene.cycles.samples
        }}

        print(f"{_START_MARKER}{{json.dumps(attributes)}}{_END_MARKER}")
    """
    return textwrap.dedent(code)


def get_scene_attributes(blender, input_file):
    # If you put `--python-expr` before the input file then you'll get values from the default cube scene.
    result = subprocess.run([
        blender,
        "--background",
        input_file,
        "--python-expr", _get_python_expr(),
    ], check=True, capture_output=True, text=True)
    json_str = _MATCHER.search(result.stdout).group(1)
    return json.loads(json_str)
