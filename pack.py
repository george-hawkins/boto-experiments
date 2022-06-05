import os
import subprocess
import textwrap


def _get_python_expr(output_file):
    code = f"""
        import sys
        import traceback
        import bpy

        try:
            bpy.ops.file.pack_all()
            bpy.ops.wm.save_as_mainfile(filepath="{output_file}", compress=True, copy=True)
        except Exception:
            traceback.print_exc()
            sys.exit(1)
    """
    return textwrap.dedent(code)


def pack_blend_file(blender, input_file, output_file):
    subprocess.run([
        blender,
        "--background",
        input_file,
        "--python-expr", _get_python_expr(output_file)
    ], cwd=os.path.dirname(input_file), check=True)
