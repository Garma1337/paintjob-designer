# coding: utf-8

from typing import Any, Callable


class Container:
    """
    Resolves services by name. Each service is registered as a factory lambda
    that receives the container, enabling dependency wiring between services.
    Instances are created once on first access and cached.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[["Container"], Any]] = {}
        self._instances: dict[str, Any] = {}

    def register(self, name: str, factory: Callable[["Container"], Any]) -> None:
        """Register a service factory. Factory receives the container for resolving deps."""
        self._factories[name] = factory
        self._instances.pop(name, None)

    def resolve(self, name: str) -> Any:
        """Resolve a service by name. Creates on first call, caches thereafter."""
        if name not in self._instances:
            if name not in self._factories:
                raise KeyError(f"No service registered for '{name}'")

            self._instances[name] = self._factories[name](self)

        return self._instances[name]
