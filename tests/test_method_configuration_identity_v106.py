from tests_support import build_fixed_memory_method, build_self_evolving_memory_method
import unittest

from methods.self_evolving_memory import (
    SelfEvolvingMemoryImplementation,
    SelfEvolvingMemoryRuntime,
)
from research_platform.participant.method.api import MethodRuntimeIdentity
from research_platform.participant.method.runtime import MethodRuntimeEndpoint
from tests_support import context_action_runtime_bindings, frozen_runtime_manifest, run_launch_manifest


class MethodConfigurationIdentityV106Tests(unittest.TestCase):
    def test_default_sem_composition_has_stable_frozen_digest(self):
        a=build_fixed_memory_method().identity
        b=build_fixed_memory_method().identity
        self.assertEqual(a.artifact_digest,b.artifact_digest)
        self.assertEqual(len(a.artifact_digest),64)

    def test_custom_evolution_provider_requires_explicit_stable_identity(self):
        class Factory:
            def __call__(self,source): raise AssertionError
        with self.assertRaises(TypeError):
            build_self_evolving_memory_method(evolution_factory=Factory())
        method=build_self_evolving_memory_method(evolution_factory=Factory(),evolution_provider_id="meta.v7")
        other=build_self_evolving_memory_method(evolution_factory=Factory(),evolution_provider_id="rule.v3")
        self.assertNotEqual(method.identity.artifact_digest,other.identity.artifact_digest)

    def test_sem_runtime_identity_does_not_depend_on_scientific_provider_selection(self):
        class Factory:
            def __call__(self, source): raise AssertionError
        baseline = build_fixed_memory_method()
        custom = build_self_evolving_memory_method(
            evolution_factory=Factory(),
            evolution_provider_id="meta.v7",
        )
        self.assertNotEqual(baseline.identity, custom.identity)
        self.assertEqual(baseline.runtime_identity, custom.runtime_identity)

    def test_sem_implementation_has_no_session_lifecycle_authority(self):
        implementation=build_fixed_memory_method().implementation
        self.assertFalse(hasattr(implementation,"open_session"))
        endpoint=build_fixed_memory_method()
        self.assertIsInstance(endpoint,MethodRuntimeEndpoint)
        self.assertIsInstance(endpoint.implementation,SelfEvolvingMemoryImplementation)
        self.assertIsInstance(endpoint.runtime,SelfEvolvingMemoryRuntime)

    def test_endpoint_keeps_implementation_identity_separate_from_runtime_binding(self):
        implementation=build_fixed_memory_method().implementation
        class RuntimeA:
            runtime_identity=MethodRuntimeIdentity("runtime.a","1","abi1","a"*64)
            def open_session(self,implementation,*,binding,session_id,services): raise AssertionError
        class RuntimeB:
            runtime_identity=MethodRuntimeIdentity("runtime.b","1","abi1","b"*64)
            def open_session(self,implementation,*,binding,session_id,services): raise AssertionError
        a=MethodRuntimeEndpoint(implementation,RuntimeA())
        b=MethodRuntimeEndpoint(implementation,RuntimeB())
        self.assertEqual(a.identity,b.identity)
        self.assertNotEqual(a.runtime_identity,b.runtime_identity)
        self.assertNotEqual(a.binding_digest,b.binding_digest)

    def test_run_launch_manifest_changes_when_runtime_binding_configuration_changes(self):
        a=run_launch_manifest(participant_bindings=context_action_runtime_bindings(method_id="sem", method_config="A"))
        b=run_launch_manifest(participant_bindings=context_action_runtime_bindings(method_id="sem", method_config="B"))
        self.assertEqual(a.participant_implementation_inventory_digest, b.participant_implementation_inventory_digest)
        self.assertNotEqual(a.participant_binding_manifest_digest, b.participant_binding_manifest_digest)
        self.assertNotEqual(a.digest(),b.digest())

    def test_frozen_runtime_manifest_changes_when_runtime_binding_configuration_changes(self):
        a=frozen_runtime_manifest(participant_bindings=context_action_runtime_bindings(method_id="sem", method_config="A"))
        b=frozen_runtime_manifest(participant_bindings=context_action_runtime_bindings(method_id="sem", method_config="B"))
        self.assertEqual(a.participant_implementation_inventory_digest, b.participant_implementation_inventory_digest)
        self.assertNotEqual(a.participant_binding_manifest_digest, b.participant_binding_manifest_digest)
        self.assertNotEqual(a.digest(),b.digest())


if __name__=='__main__':
    unittest.main()
