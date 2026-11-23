"""CalibraUV: UV-Vis calibration curves (Beer-Lambert law).

Open-source project (MIT) designed mostly with the help of Claude (Anthropic)
and reviewed by humans. See RESPONSIBLE_AI_POLICY.md.
"""

__version__ = "0.5.0"

from .engine import available_engines, compute  # noqa: F401
