import subprocess
import textwrap
import os.path
import glob

# OPTIX actually seems to be slower than CUDA on the EC2 V100 cards.
# And, just as odd, "CUDA+CPU" seems to be slower than just "CUDA" on its own.
_CYCLES_DEVICE = "CUDA"


def _get_python_expr(samples):
    code = f"""
        import bpy
        
        bpy.context.scene.cycles.samples = {samples}
    """
    return textwrap.dedent(code)


def render_blend_file_frame(blender, input_file, samples, frame, output_prefix="frame-"):
    if os.path.isabs(output_prefix):
        raise RuntimeError(f"absolute output prefixes are not supported - {output_prefix}")

    def get_output_files():
        return set(glob.iglob(glob.escape(output_prefix) + "*"))

    existing = get_output_files()
    if len(existing) != 0:
        # Frames, that were not deleted after being uploaded, have been left lying around.
        raise RuntimeError(f"frame(s) {existing} must be removed")

    subprocess.run([
        blender,
        "--background",
        input_file,
        "--python-expr", _get_python_expr(samples),
        "-E", "CYCLES",
        "-o", f"//{output_prefix}",
        "-f", str(frame),
        "--",
        "--cycles-device", _CYCLES_DEVICE
    ], check=True)

    output_file = get_output_files()

    if len(output_file) != 1:
        # Maybe multiple workers are accidentally running concurrently.
        raise RuntimeError("couldn't determine output file")

    return next(iter(output_file))
