from __future__ import annotations

from research_platform.runtime.service.api import ServiceLaunchContract
from service_os_test_support import make_service_supervisor

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

from research_platform.runtime.service.runtime.state_storage import FileServiceStateStore
from research_platform.runtime.service.runtime import (
    DirectoryCapturePathProvider,
    ExactServiceSupervisor,
    LinuxProcessBackend,
    LocalServiceProcessAdapter,
    MaterializedServiceEnvironment,
    ProcessAliveReadinessProbe,
    ServicePhase,
    ServiceProcessDrift,
    StaticServiceEnvironmentProvider,
)


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def contract(root: Path, environment: MaterializedServiceEnvironment) -> ServiceLaunchContract:
    executable = str(Path(sys.executable).resolve())
    code = "import os,time; print(os.environ['RP_SENTINEL'], flush=True); time.sleep(60)"
    return ServiceLaunchContract(
        "study.worker","g1",executable,(executable,"-c",code),str(root),
        environment.digest,h("artifact"),h("runtime"),5.0,1.0,0.2,
    )


class LocalServiceProcessV110Tests(unittest.TestCase):
    def test_exact_local_process_can_start_reconcile_and_stop_without_host_env_merge(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            environment=MaterializedServiceEnvironment.from_mapping(
                {"RP_SENTINEL":"frozen-value"}, "env:evidence"
            )
            c=contract(root,environment)
            backend=LinuxProcessBackend()
            adapter=LocalServiceProcessAdapter(
                StaticServiceEnvironmentProvider((environment,)),
                DirectoryCapturePathProvider(root/"captures"),
                backend,
                ProcessAliveReadinessProbe(poll_interval_s=0.01),
            )
            state=FileServiceStateStore(root/"state.json")
            supervisor=make_service_supervisor(state,adapter)
            report=supervisor.start_exact(c)
            self.assertEqual(report.state.phase,ServicePhase.RUNNING)
            process=report.state.process
            self.assertIsNotNone(process)
            try:
                reconciled,refs=adapter.reconcile(state.read(),c)
                self.assertEqual(reconciled,process)
                self.assertTrue(any(ref.startswith("proc-reconcile:") for ref in refs))
                actual_env=(Path("/proc")/str(process.pid)/"environ").read_bytes()
                self.assertIn(b"RP_SENTINEL=frozen-value",actual_env)
                # The child receives the frozen environment only, not arbitrary host variables.
                if "HOME" not in environment.as_dict():
                    self.assertNotIn(b"HOME=",actual_env)
            finally:
                stopped=supervisor.stop_exact(c)
                self.assertEqual(stopped.phase,ServicePhase.EXITED)

    def test_materialized_environment_drift_fails_before_spawn(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            good=MaterializedServiceEnvironment.from_mapping({"A":"1"},"good")
            wrong=MaterializedServiceEnvironment.from_mapping({"A":"2"},"wrong")

            class LyingProvider:
                def resolve(self,digest): return wrong

            adapter=LocalServiceProcessAdapter(
                LyingProvider(),DirectoryCapturePathProvider(root/"captures"),LinuxProcessBackend(),ProcessAliveReadinessProbe()
            )
            with self.assertRaises(ServiceProcessDrift):
                adapter.start(contract(root,good))

    def test_pid_start_identity_mismatch_is_treated_as_missing_not_adopted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            environment=MaterializedServiceEnvironment.from_mapping({"A":"1"},"env")
            c=contract(root,environment)
            backend=LinuxProcessBackend()
            adapter=LocalServiceProcessAdapter(
                StaticServiceEnvironmentProvider((environment,)),DirectoryCapturePathProvider(root/"captures"),backend,ProcessAliveReadinessProbe()
            )
            process,_=adapter.start(c)
            try:
                fake=replace(process,start_identity=process.start_identity+":wrong")
                state=FileServiceStateStore(root/"fake-state.json")
                from research_platform.runtime.service.runtime import ServiceSupervisorState
                state.write(replace(ServiceSupervisorState.initial(c.service_id,c.digest()),process=fake))
                reconciled,refs=adapter.reconcile(state.read(),c)
                self.assertIsNone(reconciled)
                self.assertTrue(any(ref.startswith("proc-pid-reused:") for ref in refs))
            finally:
                adapter.stop(process,c)


if __name__ == "__main__": unittest.main()
