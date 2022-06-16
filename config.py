import configparser
import os


def get_config(config_filename):
    # Basic interpolation uses the format '%(name)s' - yes, the 's' is really part of it.
    # So instead the less bizarre extended version, that uses '${name}', is used here.
    # `os.environ` is passed in so things like '${HOME}' are automatically available.
    config = configparser.ConfigParser(os.environ, interpolation=configparser.ExtendedInterpolation())
    config.read(config_filename)
    return config["DEFAULT"]
