# Copyright 2023 Robert Haschke
# Licensed under the Apache License, Version 2.0

import os
from pathlib import Path

from colcon_core.argument_parser import ArgumentParserDecoratorExtensionPoint
from colcon_core.argument_parser.action_collector import ActionCollectorDecorator
from colcon_core.logging import colcon_logger
from colcon_core.plugin_system import satisfies_version

logger = colcon_logger.getChild(__name__)
ROOT_MARKER = ".colcon_root"


class TopLevelWorkspaceArgumentParserDecorator(ArgumentParserDecoratorExtensionPoint):
    """Replace folder arguments with top-level workspace folders"""

    # Lower priority to appear as close to time-of-use as possible
    PRIORITY = 75

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            ArgumentParserDecoratorExtensionPoint.EXTENSION_POINT_VERSION, "^1.0"
        )
        get_workspace_root()

    def decorate_argument_parser(self, *, parser):  # noqa: D102
        return TopLevelWorkspaceArgumentDecorator(parser)


class TopLevelWorkspaceArgumentDecorator(ActionCollectorDecorator):
    """Change to a top-level workspace if one is found."""

    # arguments to resolve from the top-level workspace
    ROOT_FOLDER_ARGS = [
        "--build-base",
        "--install-base",
        "--log-base",
        "--test-result-base",
    ]

    def add_argument(self, *args, **kwargs):
        def add_type_resolver(kwargs, func):
            if "type" in kwargs:
                old = kwargs["type"]
                kwargs["type"] = lambda arg: old(func(arg))
            else:
                kwargs["type"] = func

        def resolve_path(value):
            if value is None:
                return value
            return os.path.abspath(os.path.join(get_workspace_root(), str(value)))

        def resolve_root_argument(value):
            if value == "ROOT":
                return str(get_workspace_root())
            return value

        for arg in self.ROOT_FOLDER_ARGS:
            if arg in args:
                add_type_resolver(kwargs, resolve_path)

        for arg in ["--base-paths"]:
            if arg in args:
                add_type_resolver(kwargs, resolve_root_argument)

        return super().add_argument(*args, **kwargs)


_root_path = None


def get_workspace_root():
    """Find colcon workspace root: either from existence of ROOT_MARKER or folders log, build, and install"""
    global _root_path
    if _root_path is not None:
        return _root_path

    def is_root(path):
        if (path / ROOT_MARKER).is_file():
            return True
        return all([(path / folder).is_dir() for folder in ["log", "build", "install"]])

    # get logical working directory (with symlinks not resolved)
    path = os.environ.get("PWD")

    path = Path(path) if path is not None else Path.cwd()
    _root_path = path
    anchor = Path(path.anchor)
    while True:
        if is_root(path):  # root path found
            _root_path = path
            break
        path = path.parent
        if path == anchor:
            break  # no root path found

    if _root_path != Path.cwd():  # inform user about root path
        print(f"Using workspace root {_root_path}", file=os.sys.stderr)

    marker = _root_path / ROOT_MARKER
    if not marker.is_file():
        logger.info(f"Marking root folder: {_root_path}")
        marker.touch()

    # set default log path
    if not os.environ.get("COLCON_LOG_PATH"):
        os.environ["COLCON_LOG_PATH"] = str(_root_path / "log")
    return _root_path
