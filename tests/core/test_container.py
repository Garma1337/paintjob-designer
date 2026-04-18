# coding: utf-8

import pytest

from paintjob_designer.core.container import Container


class TestRegister:

    def test_register_adds_factory(self):
        container = Container()
        container.register("svc", lambda c: object())

        assert container.resolve("svc") is not None

    def test_register_replaces_existing(self):
        container = Container()
        container.register("svc", lambda c: "first")
        container.resolve("svc")

        container.register("svc", lambda c: "second")

        assert container.resolve("svc") == "second"


class TestResolve:

    def test_resolves_registered_service(self):
        container = Container()
        container.register("svc", lambda c: "value")

        assert container.resolve("svc") == "value"

    def test_caches_instance_on_first_resolve(self):
        container = Container()
        container.register("svc", lambda c: object())

        first = container.resolve("svc")
        second = container.resolve("svc")

        assert first is second

    def test_raises_for_unknown_service(self):
        container = Container()

        with pytest.raises(KeyError, match="No service registered for 'missing'"):
            container.resolve("missing")

    def test_resolves_dependencies_via_container(self):
        container = Container()
        container.register("dep", lambda c: "dep-value")
        container.register("svc", lambda c: {"dep": c.resolve("dep")})

        assert container.resolve("svc") == {"dep": "dep-value"}
