from __future__ import annotations

from dataclasses import asdict

from research_platform.platform.composition.diagnostic_io import (
    build_causal_graph,
    build_debug_snapshot,
    build_diagnostic_status,
    build_triage_plan,
    diagnose_failure,
    diagnostic_last_writer,
    diagnostic_timeline,
    inspect_diagnostic_index,
    locate_diagnostic_object,
    open_diagnostic_evidence,
    publish_crash_bundle,
    rebuild_diagnostic_index,
    verify_diagnostic_evidence,
)


_COMMANDS = {
    "index-status", "rebuild-index", "verify-evidence", "status", "locate", "why", "graph",
    "timeline", "last-writer", "unclosed-operations", "crash-bundle", "debug-snapshot", "triage-plan",
}


def route_diagnostics(args: object):
    command = getattr(args, "command", None)
    if command not in _COMMANDS:
        return None
    if command == "index-status":
        return inspect_diagnostic_index(args.root)
    if command == "rebuild-index":
        return rebuild_diagnostic_index(args.root)
    if command == "crash-bundle":
        return publish_crash_bundle(args.root, args.failure_id, args.output)

    with open_diagnostic_evidence(args.root) as evidence:
        if command == "verify-evidence":
            return verify_diagnostic_evidence(evidence)
        if command == "status":
            return build_diagnostic_status(
                evidence,
                model_state=args.model_state,
                study_state=args.study_state,
            ).to_dict()
        if command == "locate":
            return locate_diagnostic_object(evidence, args.object_id)
        if command == "why":
            result = diagnose_failure(evidence, args.failure_id)
            return result if not args.graph else {
                "diagnosis": asdict(result),
                "causal_graph": asdict(build_causal_graph(evidence, args.failure_id)),
            }
        if command == "graph":
            return build_causal_graph(evidence, args.object_id, related_limit=args.limit)
        if command == "timeline":
            return diagnostic_timeline(evidence, args.object_id, seconds=args.seconds)
        if command == "last-writer":
            return diagnostic_last_writer(evidence, args.run_id, args.state_name)
        if command == "unclosed-operations":
            return evidence.unclosed_operations(run_id=args.run_id, limit=args.limit)
        if command == "debug-snapshot":
            return build_debug_snapshot(
                evidence,
                args.object_id,
                seconds=args.seconds,
                telemetry_db=args.telemetry_db,
                metric_limit=args.metric_limit,
            )
        if command == "triage-plan":
            return build_triage_plan(evidence, args.failure_id)
    raise AssertionError(command)


__all__ = ["route_diagnostics"]
