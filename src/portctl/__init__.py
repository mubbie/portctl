"""portctl — manage your ports.

A cross-platform CLI for viewing, inspecting, and killing processes on TCP ports.
Uses psutil for cross-platform support (macOS, Linux, Windows).
"""

from importlib.metadata import version

__version__ = version("portctl")
