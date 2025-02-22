# (C) Datadog, Inc. 2021-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from typing import Any, Dict

from datadog_checks.base.stubs.aggregator import AggregatorStub
from datadog_checks.datadog_cluster_agent import DatadogClusterAgentCheck
from datadog_checks.dev.utils import get_metadata_metrics

NAMESPACE = 'datadog.cluster_agent'

METRICS = [
    'admission_webhooks.certificate_expiry',
    'admission_webhooks.mutation_attempts',
    'admission_webhooks.mutation_errors',
    'admission_webhooks.reconcile_errors',
    'admission_webhooks.reconcile_success',
    'admission_webhooks.webhooks_received',
    'aggregator.flush',
    'aggregator.processed',
    'api_requests',
    'cluster_checks.busyness',
    'cluster_checks.configs_dangling',
    'cluster_checks.configs_dispatched',
    'cluster_checks.failed_stats_collection',
    'cluster_checks.nodes_reporting',
    'cluster_checks.rebalancing_decisions',
    'cluster_checks.rebalancing_duration_seconds',
    'cluster_checks.successful_rebalancing_moves',
    'cluster_checks.updating_stats_duration_seconds',
    'datadog.rate_limit_queries.limit',
    'datadog.rate_limit_queries.period',
    'datadog.rate_limit_queries.remaining',
    'datadog.rate_limit_queries.reset',
    'datadog.requests',
    'external_metrics',
    'external_metrics.delay_seconds',
    'external_metrics.processed_value',
    'go.goroutines',
    'go.memstats.alloc_bytes',
    'go.threads',
]


def test_check(aggregator, instance, mock_metrics_endpoint):
    # type: (AggregatorStub, Dict[str, Any]) -> None
    check = DatadogClusterAgentCheck('datadog_cluster_agent', {}, [instance])

    # dry run to build mapping for label joins
    check.check(instance)

    check.check(instance)

    for metric in METRICS:
        aggregator.assert_metric(NAMESPACE + '.' + metric)
        aggregator.assert_metric_has_tag_prefix(NAMESPACE + '.' + metric, 'is_leader:')

    aggregator.assert_all_metrics_covered()
    aggregator.assert_metrics_using_metadata(get_metadata_metrics())
