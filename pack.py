import os

from blender import run_blender


def pack_blend_file(blender, input_file, output_file):
    # Blender will fail if the output path is not absolute.
    output_file = os.path.abspath(output_file)
    code = f"""
        import sys
        import traceback
        import bpy
        
        try:
            bpy.ops.file.pack_all()
            bpy.ops.wm.save_as_mainfile(filepath="{output_file}", compress=True, copy=True)
        except Exception:
            traceback.print_exc()
            # Force Blender to exit with a non-zero exit code.
            sys.exit(1)
    """
    # Output is just captured to silence it (but it's printed if an error occurs).
    run_blender(blender, input_file, code, capture_output=True)
