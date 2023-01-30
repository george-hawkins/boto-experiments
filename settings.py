import argparse
import sys
from collections import namedtuple

from boto_basics import BotoBasics, get_s3_uri
from config import get_config
from scene_attributes import get_scene_attributes


basics = BotoBasics()

Settings = namedtuple("Settings", [
    "instance_count",
    "instance_type",
    "image_name_pattern",
    "image_owner",
    "security_group_name",
    "key_name",
    "iam_instance_profile",
    "blender",
    "file_store",
    "blender_archive",
    "blend_file",
    "frames",
    "file_format",
    "samples",
    "motion_blur",
    "interactive"
])


def _parse_args():
    # Start frame etc. are read from the .blend file - only use `--start` etc. if you want to override these.
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender-home", help="root directory of Blender installation")
    parser.add_argument("--start", type=int, help="start frame (inclusive)")
    parser.add_argument("--end", type=int, help="end frame (inclusive)")
    parser.add_argument("--step", type=int, help="step size from one frame to the next")
    parser.add_argument("--frames", help="comma separated list of frame numbers")
    parser.add_argument("--samples", type=int, help="number of samples to render for each pixel")
    parser.add_argument("--ec2-instances", type=int, dest="instance_count", help="number of EC2 instances to run")
    parser.add_argument(
        "--disable-interactive", help="disable prompting for input",
        dest="interactive", default=True, action="store_false"
    )

    motion_blur_parser = parser.add_mutually_exclusive_group(required=False)
    motion_blur_parser.add_argument("--enable-motion-blur", default=None, dest="motion_blur", action="store_true")
    motion_blur_parser.add_argument("--disable-motion-blur", default=None, dest="motion_blur", action="store_false")

    parser.add_argument("blend_file", help="the .blend file to be rendered")

    return parser.parse_args()


# Build setting by combining "settings.ini" and command line arguments.
def get_settings() -> Settings:
    config = get_config("settings.ini")

    blender_home = config.get("blender_home")
    file_store = config.get("file_store")
    blender_archive = config.get("blender_archive")
    instance_count = config.getint("instance_count")
    instance_type = config.get("instance_type")
    image_name_pattern = config.get("image_name_pattern")
    image_owner = config.get("image_owner")
    security_group_name = config.get("security_group_name")
    key_name = config.get("key_name")
    iam_instance_profile = config.get("iam_instance_profile")

    args = _parse_args()

    if args.blender_home is not None:
        blender_home = args.blender_home

    blender = f"{blender_home}/blender"
    blend_file = args.blend_file

    attrs = get_scene_attributes(blender, blend_file)

    samples = attrs["samples"] if args.samples is None else args.samples

    if args.frames is not None:
        # There seems to be no way to express this exclusivity between _one_ argument and _multiple_ arguments
        # with `ArgumentParser` (between one argument and another is possible, see `motion_blur` above).
        assert all(a is None for a in [args.start, args.end, args.step]), \
            "--frame cannot be used in combination with --start, --end or --step"
        frames = [int(s.strip()) for s in args.frames.split(",")]
    else:
        start = attrs["frame_start"]
        end = attrs["frame_end"]
        step = attrs["frame_step"]
        if args.start is not None:
            start = args.start
        if args.end is not None:
            end = args.end
        if args.step is not None:
            step = args.step
        frames = range(start, end + 1, step)

    motion_blur = attrs["motion_blur"]

    if args.motion_blur is not None:
        motion_blur = args.motion_blur
    elif not motion_blur:
        # The assumption is that it's a mistake if motion blur isn't enabled.
        sys.exit(
            f"motion blur is disabled in {blend_file}, use --disable-motion-blur "
            "to confirm this is OK or use --enable-motion-blur to enable it"
        )

    file_format = attrs["file_format"]
    if attrs["is_movie_format"]:
        sys.exit(f"the .blend file is using the movie format {file_format}, an image format like PNG or EXR must be used")

    if not file_store.startswith("s3://"):
        sys.exit(f"the file store URI should start with s3:// but is {file_store}")

    # Sanity check that the Blender archive has been copied to the file store.
    store = basics.get_bucket(file_store[5:])
    archive = store.Object(blender_archive)
    if not basics.object_exists(archive):
        sys.exit(f"{get_s3_uri(archive)} does not exist")

    # `interactive` controls prompting for input. It's not about whether Python was started in interactive (-i) mode.
    interactive = args.interactive if sys.stdin.isatty() else False

    # Override instance count if provided.
    if args.instance_count is not None:
        instance_count = args.instance_count

    # There's no point (unless you expect terrible spot instance termination rates) to start more instances than
    # there are frames to render.
    if instance_count > len(frames):
        sys.exit(f"the instance count {instance_count} must be less than or equal to the frame count {len(frames)}")

    return Settings(
        instance_count=instance_count,
        instance_type=instance_type,
        image_name_pattern=image_name_pattern,
        image_owner=image_owner,
        security_group_name=security_group_name,
        key_name=key_name,
        iam_instance_profile=iam_instance_profile,
        blender=blender,
        file_store=file_store,
        blender_archive=blender_archive,
        blend_file=blend_file,
        frames=frames,
        file_format=file_format,
        samples=samples,
        motion_blur=motion_blur,
        interactive=interactive
    )


def frames_str(frames):
    if isinstance(frames, range):
        s = f"frames = {frames.start} to {frames.stop - 1} inclusive"
        return s if frames.step == 1 else f"{s}, steps = {frames.step}"
    else:
        return f"frames = {frames}"
