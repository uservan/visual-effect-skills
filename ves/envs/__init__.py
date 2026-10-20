"""Desktop environment backends.  Actions are backend-neutral dicts produced by ves.actions.to_backend_action."""
from .base import DesktopEnv, EnvError


def make_env(spec: dict) -> DesktopEnv:
    """spec["backend"]: "sif" (CUA-World tasks in a rootless Singularity desktop; used on ABCI), "gym_anything"
    (gym-anything's own runners: Docker or QEMU, which need root or KVM) or "mock" (tests)."""
    backend = spec.get("backend", "sif")
    if backend == "sif":
        from .sif_desktop import SifDesktop
        return SifDesktop(spec)
    if backend == "gym_anything":
        from .gym_anything_env import GymAnythingDesktop
        return GymAnythingDesktop(spec)
    if backend == "mock":
        from .mock_env import MockDesktop
        return MockDesktop(spec)
    raise ValueError(f"unknown environment backend {backend!r}")


__all__ = ["DesktopEnv", "EnvError", "make_env"]
