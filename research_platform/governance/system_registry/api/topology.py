from __future__ import annotations

import json
from dataclasses import replace
from functools import lru_cache
from importlib.resources import files

from .contracts import (
    STANDARD_SYSTEM_SHAPE,
    AuthorityDescriptor,
    SystemDescriptor,
    SystemIdentity,
    SystemLayer,
)

_SYSTEM_TOPOLOGY: tuple[SystemDescriptor, ...] = (
    SystemDescriptor(
        identity=SystemIdentity('artifact', ()),
        layer=SystemLayer('artifact'),
        package_prefix='research_platform.artifact',
        authorities=(AuthorityDescriptor('artifact_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('data', ()),
        layer=SystemLayer('data'),
        package_prefix='research_platform.data',
        authorities=(AuthorityDescriptor('data_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ()),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment',
        authorities=(AuthorityDescriptor('environment_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('execution', ()),
        layer=SystemLayer('execution'),
        package_prefix='research_platform.execution',
        authorities=(AuthorityDescriptor('execution_operations'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ()),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation',
        authorities=(AuthorityDescriptor('experimentation_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ()),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance',
        authorities=(AuthorityDescriptor('governance_policy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ()),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model',
        authorities=(AuthorityDescriptor('model_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ()),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability',
        authorities=(AuthorityDescriptor('observability'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('operator', ()),
        layer=SystemLayer('operator'),
        package_prefix='research_platform.operator',
        authorities=(AuthorityDescriptor('operator_surface'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('participant', ()),
        layer=SystemLayer('participant'),
        package_prefix='research_platform.participant',
        authorities=(AuthorityDescriptor('participant_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('platform', ()),
        layer=SystemLayer('platform'),
        package_prefix='research_platform.platform',
        authorities=(AuthorityDescriptor('platform_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('portfolio', ()),
        layer=SystemLayer('portfolio'),
        package_prefix='research_platform.portfolio',
        authorities=(AuthorityDescriptor('portfolio_metadata'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ()),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability',
        authorities=(AuthorityDescriptor('reliability_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('resource', ()),
        layer=SystemLayer('resource'),
        package_prefix='research_platform.resource',
        authorities=(AuthorityDescriptor('resource_inventory'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ()),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime',
        authorities=(AuthorityDescriptor('runtime_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scientific', ()),
        layer=SystemLayer('scientific'),
        package_prefix='research_platform.scientific',
        authorities=(AuthorityDescriptor('scientific_method'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scope', ()),
        layer=SystemLayer('scope'),
        package_prefix='research_platform.scope',
        authorities=(AuthorityDescriptor('scope_tree'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('artifact', ('catalog',)),
        layer=SystemLayer('artifact'),
        package_prefix='research_platform.artifact.catalog',
        authorities=(AuthorityDescriptor('artifact_catalog'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('artifact', ('content',)),
        layer=SystemLayer('artifact'),
        package_prefix='research_platform.artifact.content',
        authorities=(AuthorityDescriptor('artifact_content'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('artifact', ('lineage',)),
        layer=SystemLayer('artifact'),
        package_prefix='research_platform.artifact.lineage',
        authorities=(AuthorityDescriptor('artifact_lineage'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('artifact', ('reference',)),
        layer=SystemLayer('artifact'),
        package_prefix='research_platform.artifact.reference',
        authorities=(AuthorityDescriptor('artifact_reference'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('artifact', ('retention',)),
        layer=SystemLayer('artifact'),
        package_prefix='research_platform.artifact.retention',
        authorities=(AuthorityDescriptor('artifact_retention'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('data', ('dataset',)),
        layer=SystemLayer('data'),
        package_prefix='research_platform.data.dataset',
        authorities=(AuthorityDescriptor('dataset_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('data', ('fact',)),
        layer=SystemLayer('data'),
        package_prefix='research_platform.data.fact',
        authorities=(AuthorityDescriptor('fact_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('data', ('projection',)),
        layer=SystemLayer('data'),
        package_prefix='research_platform.data.projection',
        authorities=(AuthorityDescriptor('projection_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('data', ('query',)),
        layer=SystemLayer('data'),
        package_prefix='research_platform.data.query',
        authorities=(AuthorityDescriptor('query_contracts'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('data', ('record',)),
        layer=SystemLayer('data'),
        package_prefix='research_platform.data.record',
        authorities=(AuthorityDescriptor('record_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('data', ('state',)),
        layer=SystemLayer('data'),
        package_prefix='research_platform.data.state',
        authorities=(AuthorityDescriptor('state_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('binding',)),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.binding',
        authorities=(AuthorityDescriptor('environment_binding'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('catalog',)),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.catalog',
        authorities=(AuthorityDescriptor('environment_catalog'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('instance',)),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.instance',
        authorities=(AuthorityDescriptor('environment_instance'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('minecraft',)),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.minecraft',
        authorities=(AuthorityDescriptor('minecraft_environment'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('python',)),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.python',
        authorities=(AuthorityDescriptor('python_environment'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('resolution',)),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.resolution',
        authorities=(AuthorityDescriptor('environment_resolution'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('runtime',)),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.runtime',
        authorities=(AuthorityDescriptor('environment_runtime_contract'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('specification',)),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.specification',
        authorities=(AuthorityDescriptor('environment_spec'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('execution', ('admission',)),
        layer=SystemLayer('execution'),
        package_prefix='research_platform.execution.admission',
        authorities=(AuthorityDescriptor('admission_decision'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('execution', ('capability',)),
        layer=SystemLayer('execution'),
        package_prefix='research_platform.execution.capability',
        authorities=(AuthorityDescriptor('capability_catalog'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('execution', ('command',)),
        layer=SystemLayer('execution'),
        package_prefix='research_platform.execution.command',
        authorities=(AuthorityDescriptor('command_intent'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('execution', ('operation',)),
        layer=SystemLayer('execution'),
        package_prefix='research_platform.execution.operation',
        authorities=(AuthorityDescriptor('operation_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('execution', ('scheduling',)),
        layer=SystemLayer('execution'),
        package_prefix='research_platform.execution.scheduling',
        authorities=(AuthorityDescriptor('schedule_intent'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('execution', ('workflow',)),
        layer=SystemLayer('execution'),
        package_prefix='research_platform.execution.workflow',
        authorities=(AuthorityDescriptor('workflow_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('branch',)),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.branch',
        authorities=(AuthorityDescriptor('branch_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('checkpoint',)),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.checkpoint',
        authorities=(AuthorityDescriptor('checkpoint_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('experiment',)),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.experiment',
        authorities=(AuthorityDescriptor('experiment_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('run',)),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.run',
        authorities=(AuthorityDescriptor('run_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('study',)),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.study',
        authorities=(AuthorityDescriptor('study_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('variant',)),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.variant',
        authorities=(AuthorityDescriptor('variant_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ('architecture',)),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance.architecture',
        authorities=(AuthorityDescriptor('architecture_policy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ('quality',)),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance.quality',
        authorities=(AuthorityDescriptor('quality_policy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ('release',)),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance.release',
        authorities=(AuthorityDescriptor('release_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ('schema',)),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance.schema',
        authorities=(AuthorityDescriptor('schema_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ('security',)),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance.security',
        authorities=(AuthorityDescriptor('security_policy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ('system_registry',)),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance.system_registry',
        authorities=(AuthorityDescriptor('system_topology'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('asset',)),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.asset',
        authorities=(AuthorityDescriptor('model_asset'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('assignment',)),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.assignment',
        authorities=(AuthorityDescriptor('model_assignment'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('catalog',)),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.catalog',
        authorities=(AuthorityDescriptor('model_catalog'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('deployment',)),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.deployment',
        authorities=(AuthorityDescriptor('model_deployment'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('qualification',)),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.qualification',
        authorities=(AuthorityDescriptor('model_qualification'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('request',)),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.request',
        authorities=(AuthorityDescriptor('model_request'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('serving',)),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.serving',
        authorities=(AuthorityDescriptor('model_serving'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('stack',)),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.stack',
        authorities=(AuthorityDescriptor('model_stack'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('capture',)),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.capture',
        authorities=(AuthorityDescriptor('capture_observation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('diagnostic',)),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.diagnostic',
        authorities=(AuthorityDescriptor('diagnostic_view_contract'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging',)),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging',
        authorities=(AuthorityDescriptor('log_observation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('projection',)),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.projection',
        authorities=(AuthorityDescriptor('observation_projection'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('status',)),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.status',
        authorities=(AuthorityDescriptor('status_observation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('telemetry',)),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.telemetry',
        authorities=(AuthorityDescriptor('telemetry_observation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('tracing',)),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.tracing',
        authorities=(AuthorityDescriptor('trace_observation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('operator', ('audit',)),
        layer=SystemLayer('operator'),
        package_prefix='research_platform.operator.audit',
        authorities=(AuthorityDescriptor('operator_audit'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('operator', ('command',)),
        layer=SystemLayer('operator'),
        package_prefix='research_platform.operator.command',
        authorities=(AuthorityDescriptor('operator_commands'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('operator', ('incident',)),
        layer=SystemLayer('operator'),
        package_prefix='research_platform.operator.incident',
        authorities=(AuthorityDescriptor('operator_incident_view'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('operator', ('maintenance',)),
        layer=SystemLayer('operator'),
        package_prefix='research_platform.operator.maintenance',
        authorities=(AuthorityDescriptor('operator_maintenance'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('operator', ('query',)),
        layer=SystemLayer('operator'),
        package_prefix='research_platform.operator.query',
        authorities=(AuthorityDescriptor('operator_queries'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('participant', ('agent',)),
        layer=SystemLayer('participant'),
        package_prefix='research_platform.participant.agent',
        authorities=(AuthorityDescriptor('agent_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('participant', ('binding',)),
        layer=SystemLayer('participant'),
        package_prefix='research_platform.participant.binding',
        authorities=(AuthorityDescriptor('participant_binding'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('participant', ('capability',)),
        layer=SystemLayer('participant'),
        package_prefix='research_platform.participant.capability',
        authorities=(AuthorityDescriptor('participant_capability'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('participant', ('definition',)),
        layer=SystemLayer('participant'),
        package_prefix='research_platform.participant.definition',
        authorities=(AuthorityDescriptor('participant_definition'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('participant', ('method',)),
        layer=SystemLayer('participant'),
        package_prefix='research_platform.participant.method',
        authorities=(AuthorityDescriptor('method_participant_binding'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('participant', ('session',)),
        layer=SystemLayer('participant'),
        package_prefix='research_platform.participant.session',
        authorities=(AuthorityDescriptor('participant_session'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('platform', ('configuration',)),
        layer=SystemLayer('platform'),
        package_prefix='research_platform.platform.configuration',
        authorities=(AuthorityDescriptor('platform_configuration'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('platform', ('identity',)),
        layer=SystemLayer('platform'),
        package_prefix='research_platform.platform.identity',
        authorities=(AuthorityDescriptor('platform_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('platform', ('lifecycle',)),
        layer=SystemLayer('platform'),
        package_prefix='research_platform.platform.lifecycle',
        authorities=(AuthorityDescriptor('platform_lifecycle'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('portfolio', ('membership',)),
        layer=SystemLayer('portfolio'),
        package_prefix='research_platform.portfolio.membership',
        authorities=(AuthorityDescriptor('portfolio_membership'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('portfolio', ('program',)),
        layer=SystemLayer('portfolio'),
        package_prefix='research_platform.portfolio.program',
        authorities=(AuthorityDescriptor('program_metadata'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('portfolio', ('project',)),
        layer=SystemLayer('portfolio'),
        package_prefix='research_platform.portfolio.project',
        authorities=(AuthorityDescriptor('project_metadata'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('portfolio', ('workspace',)),
        layer=SystemLayer('portfolio'),
        package_prefix='research_platform.portfolio.workspace',
        authorities=(AuthorityDescriptor('workspace_metadata'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('diagnostics',)),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.diagnostics',
        authorities=(AuthorityDescriptor('diagnostic_queries'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('effect',)),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.effect',
        authorities=(AuthorityDescriptor('effect_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('failure',)),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.failure',
        authorities=(AuthorityDescriptor('failure_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('forensics',)),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.forensics',
        authorities=(AuthorityDescriptor('forensic_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('incident',)),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.incident',
        authorities=(AuthorityDescriptor('incident_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('policy',)),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.policy',
        authorities=(AuthorityDescriptor('reliability_policy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('reconciliation',)),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.reconciliation',
        authorities=(AuthorityDescriptor('reconciliation_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('recovery',)),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.recovery',
        authorities=(AuthorityDescriptor('recovery_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('resource', ('allocation',)),
        layer=SystemLayer('resource'),
        package_prefix='research_platform.resource.allocation',
        authorities=(AuthorityDescriptor('resource_allocation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('resource', ('catalog',)),
        layer=SystemLayer('resource'),
        package_prefix='research_platform.resource.catalog',
        authorities=(AuthorityDescriptor('resource_catalog'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('resource', ('compute',)),
        layer=SystemLayer('resource'),
        package_prefix='research_platform.resource.compute',
        authorities=(AuthorityDescriptor('compute_inventory'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('resource', ('directory',)),
        layer=SystemLayer('resource'),
        package_prefix='research_platform.resource.directory',
        authorities=(AuthorityDescriptor('directory_inventory'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('resource', ('lease',)),
        layer=SystemLayer('resource'),
        package_prefix='research_platform.resource.lease',
        authorities=(AuthorityDescriptor('resource_lease'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('resource', ('resolution',)),
        layer=SystemLayer('resource'),
        package_prefix='research_platform.resource.resolution',
        authorities=(AuthorityDescriptor('resource_resolution'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('control',)),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.control',
        authorities=(AuthorityDescriptor('runtime_control'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('history',)),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.history',
        authorities=(AuthorityDescriptor('runtime_history'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('host',)),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.host',
        authorities=(AuthorityDescriptor('host_runtime_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('process',)),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.process',
        authorities=(AuthorityDescriptor('process_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('server',)),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.server',
        authorities=(AuthorityDescriptor('server_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('service',)),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.service',
        authorities=(AuthorityDescriptor('service_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('session',)),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.session',
        authorities=(AuthorityDescriptor('runtime_session'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('supervision',)),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.supervision',
        authorities=(AuthorityDescriptor('supervision_state'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scientific', ('implementation',)),
        layer=SystemLayer('scientific'),
        package_prefix='research_platform.scientific.implementation',
        authorities=(AuthorityDescriptor('method_implementation_catalog'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scientific', ('measurement',)),
        layer=SystemLayer('scientific'),
        package_prefix='research_platform.scientific.measurement',
        authorities=(AuthorityDescriptor('measurement_semantics'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scientific', ('method',)),
        layer=SystemLayer('scientific'),
        package_prefix='research_platform.scientific.method',
        authorities=(AuthorityDescriptor('method_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scientific', ('prompt',)),
        layer=SystemLayer('scientific'),
        package_prefix='research_platform.scientific.prompt',
        authorities=(AuthorityDescriptor('prompt_authority'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scientific', ('protocol',)),
        layer=SystemLayer('scientific'),
        package_prefix='research_platform.scientific.protocol',
        authorities=(AuthorityDescriptor('scientific_protocol'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scope', ('hierarchy',)),
        layer=SystemLayer('scope'),
        package_prefix='research_platform.scope.hierarchy',
        authorities=(AuthorityDescriptor('scope_hierarchy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scope', ('identity',)),
        layer=SystemLayer('scope'),
        package_prefix='research_platform.scope.identity',
        authorities=(AuthorityDescriptor('scope_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scope', ('membership',)),
        layer=SystemLayer('scope'),
        package_prefix='research_platform.scope.membership',
        authorities=(AuthorityDescriptor('scope_membership'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scope', ('ownership',)),
        layer=SystemLayer('scope'),
        package_prefix='research_platform.scope.ownership',
        authorities=(AuthorityDescriptor('scope_ownership'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scope', ('path',)),
        layer=SystemLayer('scope'),
        package_prefix='research_platform.scope.path',
        authorities=(AuthorityDescriptor('scope_path'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('scope', ('resolution',)),
        layer=SystemLayer('scope'),
        package_prefix='research_platform.scope.resolution',
        authorities=(AuthorityDescriptor('scope_resolution'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('artifact', ('lineage', 'relation')),
        layer=SystemLayer('artifact'),
        package_prefix='research_platform.artifact.lineage.relation',
        authorities=(AuthorityDescriptor('artifact_lineage_edge'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('data', ('query', 'cross')),
        layer=SystemLayer('data'),
        package_prefix='research_platform.data.query.cross',
        authorities=(AuthorityDescriptor('cross_query'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('instance', 'identity')),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.instance.identity',
        authorities=(AuthorityDescriptor('environment_instance_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('instance', 'readiness')),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.instance.readiness',
        authorities=(AuthorityDescriptor('environment_readiness'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('specification', 'digest')),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.specification.digest',
        authorities=(AuthorityDescriptor('environment_digest'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('environment', ('specification', 'schema')),
        layer=SystemLayer('environment'),
        package_prefix='research_platform.environment.specification.schema',
        authorities=(AuthorityDescriptor('environment_schema'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('run', 'identity')),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.run.identity',
        authorities=(AuthorityDescriptor('run_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('run', 'lifecycle')),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.run.lifecycle',
        authorities=(AuthorityDescriptor('run_lifecycle'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('experimentation', ('run', 'manifest')),
        layer=SystemLayer('experimentation'),
        package_prefix='research_platform.experimentation.run.manifest',
        authorities=(AuthorityDescriptor('run_manifest'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ('architecture', 'authority')),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance.architecture.authority',
        authorities=(AuthorityDescriptor('authority_policy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('governance', ('architecture', 'dependency')),
        layer=SystemLayer('governance'),
        package_prefix='research_platform.governance.architecture.dependency',
        authorities=(AuthorityDescriptor('dependency_policy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('catalog', 'family')),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.catalog.family',
        authorities=(AuthorityDescriptor('model_family'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('catalog', 'revision')),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.catalog.revision',
        authorities=(AuthorityDescriptor('model_revision'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('deployment', 'closure')),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.deployment.closure',
        authorities=(AuthorityDescriptor('deployment_closure'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('request', 'input')),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.request.input',
        authorities=(AuthorityDescriptor('request_input'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('request', 'output')),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.request.output',
        authorities=(AuthorityDescriptor('request_output'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('model', ('serving', 'endpoint')),
        layer=SystemLayer('model'),
        package_prefix='research_platform.model.serving.endpoint',
        authorities=(AuthorityDescriptor('serving_endpoint'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('diagnostic', 'correlation')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.diagnostic.correlation',
        authorities=(AuthorityDescriptor('diagnostic_correlation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('diagnostic', 'query')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.diagnostic.query',
        authorities=(AuthorityDescriptor('diagnostic_query'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('diagnostic', 'snapshot')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.diagnostic.snapshot',
        authorities=(AuthorityDescriptor('diagnostic_snapshot'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'capture')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.capture',
        authorities=(AuthorityDescriptor('raw_capture'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'context')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.context',
        authorities=(AuthorityDescriptor('log_context'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'projection')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.projection',
        authorities=(AuthorityDescriptor('log_projection'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'query')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.query',
        authorities=(AuthorityDescriptor('log_query'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'record')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.record',
        authorities=(AuthorityDescriptor('log_record_schema'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'retention')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.retention',
        authorities=(AuthorityDescriptor('log_retention'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'routing')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.routing',
        authorities=(AuthorityDescriptor('log_routing'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'sink')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.sink',
        authorities=(AuthorityDescriptor('log_sink_delivery'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('logging', 'storage')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.logging.storage',
        authorities=(AuthorityDescriptor('log_storage'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('status', 'health')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.status.health',
        authorities=(AuthorityDescriptor('health_observation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('status', 'lifecycle_view')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.status.lifecycle_view',
        authorities=(AuthorityDescriptor('lifecycle_projection'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('telemetry', 'event')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.telemetry.event',
        authorities=(AuthorityDescriptor('telemetry_event'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('telemetry', 'metric')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.telemetry.metric',
        authorities=(AuthorityDescriptor('telemetry_metric'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('tracing', 'context')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.tracing.context',
        authorities=(AuthorityDescriptor('trace_context'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('tracing', 'propagation')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.tracing.propagation',
        authorities=(AuthorityDescriptor('trace_propagation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('observability', ('tracing', 'storage')),
        layer=SystemLayer('observability'),
        package_prefix='research_platform.observability.tracing.storage',
        authorities=(AuthorityDescriptor('trace_storage'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('operator', ('command', 'intent')),
        layer=SystemLayer('operator'),
        package_prefix='research_platform.operator.command.intent',
        authorities=(AuthorityDescriptor('operator_command_intent'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('operator', ('query', 'search')),
        layer=SystemLayer('operator'),
        package_prefix='research_platform.operator.query.search',
        authorities=(AuthorityDescriptor('operator_search'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('diagnostics', 'causal')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.diagnostics.causal',
        authorities=(AuthorityDescriptor('causal_diagnostics'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('diagnostics', 'timeline')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.diagnostics.timeline',
        authorities=(AuthorityDescriptor('diagnostic_timeline'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('failure', 'catalog')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.failure.catalog',
        authorities=(AuthorityDescriptor('failure_catalog'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('failure', 'descriptor')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.failure.descriptor',
        authorities=(AuthorityDescriptor('failure_descriptor'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('failure', 'envelope')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.failure.envelope',
        authorities=(AuthorityDescriptor('failure_envelope'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('failure', 'fingerprint')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.failure.fingerprint',
        authorities=(AuthorityDescriptor('failure_fingerprint'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('failure', 'materialization')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.failure.materialization',
        authorities=(AuthorityDescriptor('failure_materialization'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('failure', 'taxonomy')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.failure.taxonomy',
        authorities=(AuthorityDescriptor('failure_taxonomy'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('reconciliation', 'effect')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.reconciliation.effect',
        authorities=(AuthorityDescriptor('effect_reconciliation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('reconciliation', 'state')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.reconciliation.state',
        authorities=(AuthorityDescriptor('state_reconciliation'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('recovery', 'evidence')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.recovery.evidence',
        authorities=(AuthorityDescriptor('recovery_evidence'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('recovery', 'execution')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.recovery.execution',
        authorities=(AuthorityDescriptor('recovery_execution'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('recovery', 'plan')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.recovery.plan',
        authorities=(AuthorityDescriptor('recovery_plan'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('reliability', ('recovery', 'replay')),
        layer=SystemLayer('reliability'),
        package_prefix='research_platform.reliability.recovery.replay',
        authorities=(AuthorityDescriptor('recovery_replay'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('process', 'identity')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.process.identity',
        authorities=(AuthorityDescriptor('process_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('process', 'launch')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.process.launch',
        authorities=(AuthorityDescriptor('process_launch'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('process', 'lifecycle')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.process.lifecycle',
        authorities=(AuthorityDescriptor('process_lifecycle'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('process', 'supervision')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.process.supervision',
        authorities=(AuthorityDescriptor('process_supervision'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('server', 'health')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.server.health',
        authorities=(AuthorityDescriptor('server_health_contract'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('server', 'identity')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.server.identity',
        authorities=(AuthorityDescriptor('server_identity'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('server', 'lifecycle')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.server.lifecycle',
        authorities=(AuthorityDescriptor('server_lifecycle'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('session', 'binding')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.session.binding',
        authorities=(AuthorityDescriptor('runtime_binding'),),
    ),
    SystemDescriptor(
        identity=SystemIdentity('runtime', ('session', 'identity')),
        layer=SystemLayer('runtime'),
        package_prefix='research_platform.runtime.session.identity',
        authorities=(AuthorityDescriptor('runtime_session_identity'),),
    ),
)

_NODE_METADATA: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    'artifact': (('scope',), (), ()),
    'artifact/catalog': ((), ('artifact.registry',), ()),
    'data': (('scope',), (), ()),
    'data/dataset': ((), ('dataset.registry',), ()),
    'data/fact': ((), ('durable.fact',), ()),
    'data/projection': ((), ('projection.runtime',), ()),
    'data/record': ((), ('record.plane',), ()),
    'data/state': ((), ('state.atomic',), ()),
    'environment': (('platform', 'reliability', 'resource', 'scope'), (), ()),
    'environment/catalog': ((), ('environment.catalog',), ()),
    'environment/minecraft': (('artifact', 'environment', 'reliability', 'resource', 'runtime'), ('environment.minecraft.contract',), ()),
    'environment/python': ((), ('python-environment.registry', 'python-environment.lifecycle', 'python-environment.execution', 'python-environment.packages'), ()),
    'environment/runtime': ((), ('environment.contract',), ()),
    'execution': (('environment', 'governance', 'model', 'observability', 'participant', 'platform', 'reliability', 'runtime', 'scope'), (), ()),
    'execution/capability': ((), ('capability.invocation', 'capability.registration'), ()),
    'execution/workflow': ((), ('workflow.runtime',), ()),
    'experimentation': (('execution', 'participant', 'platform', 'scope'), (), ()),
    'experimentation/checkpoint': ((), ('run.checkpoint',), ()),
    'experimentation/experiment': ((), ('experiment.definition', 'experiment.runtime'), ()),
    'experimentation/run': ((), ('run.lifecycle', 'run.decision'), ()),
    'experimentation/study': ((), ('study.definition',), ()),
    'governance': (('platform',), (), ()),
    'governance/architecture': ((), ('architecture.audit',), ()),
    'governance/quality': ((), ('quality.audit',), ()),
    'governance/release': ((), ('release.freeze',), ()),
    'model': (('environment', 'platform', 'resource', 'runtime', 'scope'), (), ()),
    'model/asset': ((), ('model.asset', 'model.asset-acquisition'), ()),
    'model/assignment': ((), ('model.assignment',), ()),
    'model/deployment': ((), ('model.deployment', 'model.deployment-control'), ()),
    'model/request': ((), ('model.request',), ()),
    'model/serving': ((), ('model.serving', 'model.qualification'), ()),
    'observability': (('data', 'governance', 'platform', 'scope'), (), ()),
    'observability/logging': ((), ('logging.observation',), ()),
    'observability/status': ((), ('status.read-model',), ()),
    'observability/telemetry': ((), ('telemetry.metrics',), ()),
    'operator': (('environment', 'governance', 'model', 'observability', 'platform', 'reliability', 'resource', 'scope'), (), ()),
    'participant': (('data', 'platform', 'reliability'), (), ()),
    'participant/agent': ((), ('agent.contract',), ()),
    'participant/capability': ((), ('capability.contract',), ()),
    'participant/method': ((), ('method.contract', 'method.runtime'), ()),
    'portfolio': (('scope',), (), ()),
    'reliability': (('data', 'governance', 'observability', 'platform', 'scope'), (), ()),
    'reliability/diagnostics': ((), ('diagnostics.causal',), ()),
    'reliability/effect': ((), ('effect.safety', 'effect.journal'), ()),
    'reliability/failure': ((), ('failure.truth',), ()),
    'reliability/forensics': ((), ('forensics.ledger',), ()),
    'reliability/recovery': ((), ('recovery.runtime',), ()),
    'resource': (('platform', 'scope'), (), ()),
    'resource/compute': ((), ('compute.inventory', 'compute.scheduler'), ()),
    'resource/directory': ((), ('directory.layout', 'workspace.storage'), ()),
    'resource/resolution': ((), ('resource.hierarchical-resolution',), ()),
    'runtime': (('governance', 'observability', 'platform', 'reliability', 'scope'), (), ()),
    'runtime/host': ((), ('host.runtime',), ()),
    'runtime/process': ((), ('process.execution', 'process.capture'), ()),
    'runtime/service': ((), ('service.runtime',), ()),
    'runtime/session': ((), ('persistent-session.runtime',), ()),
    'scientific': (('data', 'experimentation', 'participant', 'platform'), (), ()),
}


def _apply_node_metadata(descriptor: SystemDescriptor) -> SystemDescriptor:
    metadata = _NODE_METADATA.get(descriptor.identity.key)
    if metadata is None:
        return descriptor
    requires, provides, components = metadata
    return replace(
        descriptor,
        requires=requires,
        provides=provides,
        components=components,
    )


@lru_cache(maxsize=1)
def _load_catalog_semantics() -> dict[str, dict[str, object]]:
    """Load ownership semantics from the canonical catalog document."""

    catalog_resource = files("research_platform.governance.system_registry").joinpath("catalog.json")
    try:
        raw = json.loads(catalog_resource.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("cannot load packaged canonical system catalog") from exc
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError("packaged canonical system catalog is not a non-empty object")

    required = {"authority", "must_not_own", "owns", "package_prefix", "parent", "shape"}
    result: dict[str, dict[str, object]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, dict) or set(value) != required:
            raise RuntimeError(f"invalid packaged catalog descriptor for {key!r}")
        if value["shape"] != list(STANDARD_SYSTEM_SHAPE):
            raise RuntimeError(f"unsupported packaged system shape for {key!r}")
        result[key] = value
    return result


def _apply_catalog_semantics(descriptor: SystemDescriptor) -> SystemDescriptor:
    semantics = _load_catalog_semantics().get(descriptor.identity.key)
    if semantics is None:
        raise RuntimeError(f"system descriptor missing from canonical catalog: {descriptor.identity.key}")
    authority = semantics["authority"]
    owns = semantics["owns"]
    must_not_own = semantics["must_not_own"]
    package_prefix = semantics["package_prefix"]
    parent = semantics["parent"]
    if isinstance(parent, str):
        parent = parent.replace(".", "/")
    if not all(isinstance(item, str) and item.strip() for item in (authority, owns, must_not_own, package_prefix)):
        raise RuntimeError(f"invalid ownership semantics for {descriptor.identity.key}")
    if package_prefix != descriptor.package_prefix:
        raise RuntimeError(f"package prefix drift for {descriptor.identity.key}")
    if parent != descriptor.parent_key:
        raise RuntimeError(f"parent drift for {descriptor.identity.key}")
    if descriptor.authority_id != authority:
        raise RuntimeError(f"authority drift for {descriptor.identity.key}")
    return replace(
        descriptor,
        owns=owns,
        must_not_own=must_not_own,
        shape=tuple(semantics["shape"]),
    )


SYSTEM_CATALOG: tuple[SystemDescriptor, ...] = tuple(
    _apply_catalog_semantics(_apply_node_metadata(descriptor)) for descriptor in _SYSTEM_TOPOLOGY
)


def system_catalog() -> tuple[SystemDescriptor, ...]:
    """Return the canonical recursive platform system tree.

    Topology and authority identity are contract data. Runtime registries load this
    declaration; they do not own or redefine it.
    """
    return SYSTEM_CATALOG


__all__ = ["SYSTEM_CATALOG", "system_catalog"]
