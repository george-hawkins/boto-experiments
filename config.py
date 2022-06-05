import configparser
import os


def get_config(config_filename):
    # Basic interpolation uses the format '%(name)s' - yes, the 's' is really part of it. So use
    # less bizarre extended version that uses '${name}'.
    config = configparser.ConfigParser(os.environ, interpolation=configparser.ExtendedInterpolation())
    config.read(config_filename)
    return config["DEFAULT"]


