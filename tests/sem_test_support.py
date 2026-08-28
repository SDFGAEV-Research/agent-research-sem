"""SEM-owned test composition helpers.

These helpers intentionally live downstream so project tests never extend the
upstream platform's root ``tests_support`` module.
"""

from tests_support import default_method_composition_ports


def build_fixed_memory_method(**kwargs):
    from projects.sem_paper.method.self_evolving_memory.composition import (
        build_fixed_memory_method as build,
    )

    kwargs.setdefault("system_ports", default_method_composition_ports())
    return build(**kwargs)


def build_self_evolving_memory_method(**kwargs):
    from projects.sem_paper.method.self_evolving_memory.composition import (
        build_self_evolving_memory_method as build,
    )

    kwargs.setdefault("system_ports", default_method_composition_ports())
    return build(**kwargs)
