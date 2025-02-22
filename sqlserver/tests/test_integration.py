# (C) Datadog, Inc. 2018-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from copy import copy, deepcopy

import pytest

from datadog_checks.sqlserver import SQLServer
from datadog_checks.sqlserver.connection import SQLConnectionError

from .common import CHECK_NAME, CUSTOM_METRICS, CUSTOM_QUERY_A, CUSTOM_QUERY_B, EXPECTED_DEFAULT_METRICS, assert_metrics
from .utils import not_windows_ci, windows_ci

try:
    import pyodbc
except ImportError:
    pyodbc = None


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_check_invalid_password(aggregator, dd_run_check, init_config, instance_docker):
    instance_docker['password'] = 'FOO'

    sqlserver_check = SQLServer(CHECK_NAME, init_config, [instance_docker])

    with pytest.raises(SQLConnectionError):
        sqlserver_check.initialize_connection()
        sqlserver_check.check(instance_docker)
    aggregator.assert_service_check(
        'sqlserver.can_connect',
        status=sqlserver_check.CRITICAL,
        tags=['sqlserver_host:localhost,1433', 'db:master', 'optional:tag1'],
    )


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_check_docker(aggregator, dd_run_check, init_config, instance_docker):
    sqlserver_check = SQLServer(CHECK_NAME, init_config, [instance_docker])
    dd_run_check(sqlserver_check)
    expected_tags = instance_docker.get('tags', []) + [
        'sqlserver_host:{}'.format(instance_docker.get('host')),
        'db:master',
    ]
    assert_metrics(aggregator, expected_tags)


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_check_stored_procedure(aggregator, dd_run_check, init_config, instance_docker):
    instance_pass = deepcopy(instance_docker)

    proc = 'pyStoredProc'
    sp_tags = "foo:bar,baz:qux"
    instance_pass['stored_procedure'] = proc

    sqlserver_check = SQLServer(CHECK_NAME, init_config, [instance_pass])
    dd_run_check(sqlserver_check)

    expected_tags = instance_pass.get('tags', []) + sp_tags.split(',')
    aggregator.assert_metric('sql.sp.testa', value=100, tags=expected_tags, count=1)
    aggregator.assert_metric('sql.sp.testb', tags=expected_tags, count=2)


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_check_stored_procedure_proc_if(aggregator, dd_run_check, init_config, instance_docker):
    instance_fail = deepcopy(instance_docker)
    proc = 'pyStoredProc'
    proc_only_fail = "select cntr_type from sys.dm_os_performance_counters where counter_name in ('FOO');"

    instance_fail['proc_only_if'] = proc_only_fail
    instance_fail['stored_procedure'] = proc

    sqlserver_check = SQLServer(CHECK_NAME, init_config, [instance_fail])
    dd_run_check(sqlserver_check)

    # apply a proc check that will never fail and assert that the metrics remain unchanged
    assert len(aggregator._metrics) == 0


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_custom_metrics_object_name(aggregator, dd_run_check, init_config_object_name, instance_docker):
    sqlserver_check = SQLServer(CHECK_NAME, init_config_object_name, [instance_docker])
    dd_run_check(sqlserver_check)

    aggregator.assert_metric('sqlserver.cache.hit_ratio', tags=['optional:tag1', 'optional_tag:tag1'], count=1)
    aggregator.assert_metric('sqlserver.active_requests', tags=['optional:tag1', 'optional_tag:tag1'], count=1)


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_custom_metrics_alt_tables(aggregator, dd_run_check, init_config_alt_tables, instance_docker):
    instance = deepcopy(instance_docker)
    instance['include_task_scheduler_metrics'] = False

    sqlserver_check = SQLServer(CHECK_NAME, init_config_alt_tables, [instance])
    dd_run_check(sqlserver_check)

    aggregator.assert_metric('sqlserver.LCK_M_S.max_wait_time_ms', tags=['optional:tag1'], count=1)
    aggregator.assert_metric('sqlserver.LCK_M_S.signal_wait_time_ms', tags=['optional:tag1'], count=1)
    aggregator.assert_metric(
        'sqlserver.MEMORYCLERK_BITMAP.virtual_memory_committed_kb', tags=['memory_node_id:0', 'optional:tag1'], count=1
    )
    aggregator.assert_metric(
        'sqlserver.MEMORYCLERK_BITMAP.virtual_memory_reserved_kb', tags=['memory_node_id:0', 'optional:tag1'], count=1
    )

    # check a second time for io metrics to be processed
    dd_run_check(sqlserver_check)

    aggregator.assert_metric('sqlserver.io_file_stats.num_of_reads')
    aggregator.assert_metric('sqlserver.io_file_stats.num_of_writes')


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_autodiscovery_database_metrics(aggregator, dd_run_check, instance_autodiscovery):
    instance_autodiscovery['autodiscovery_include'] = ['master', 'msdb']
    check = SQLServer(CHECK_NAME, {}, [instance_autodiscovery])
    dd_run_check(check)

    master_tags = [
        'database:master',
        'database_files_state_desc:ONLINE',
        'file_id:1',
        'file_location:/var/opt/mssql/data/master.mdf',
        'file_type:data',
        'optional:tag1',
    ]
    msdb_tags = [
        'database:msdb',
        'database_files_state_desc:ONLINE',
        'file_id:1',
        'file_location:/var/opt/mssql/data/MSDBData.mdf',
        'file_type:data',
        'optional:tag1',
    ]
    aggregator.assert_metric('sqlserver.database.files.size', tags=master_tags)
    aggregator.assert_metric('sqlserver.database.files.size', tags=msdb_tags)
    aggregator.assert_metric('sqlserver.database.files.state', tags=master_tags)
    aggregator.assert_metric('sqlserver.database.files.state', tags=msdb_tags)


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_autodiscovery_db_service_checks(aggregator, dd_run_check, instance_autodiscovery):
    instance_autodiscovery['autodiscovery_include'] = ['master', 'msdb']
    check = SQLServer(CHECK_NAME, {}, [instance_autodiscovery])
    dd_run_check(check)

    # verify that the old status check returns OK
    aggregator.assert_service_check(
        'sqlserver.can_connect',
        tags=['db:master', 'optional:tag1', 'sqlserver_host:localhost,1433'],
        status=SQLServer.OK,
    )

    # verify all databses in autodiscovery have a service check
    for database in instance_autodiscovery['autodiscovery_include']:
        aggregator.assert_service_check(
            'sqlserver.database.can_connect',
            tags=['db:{}'.format(database), 'optional:tag1', 'sqlserver_host:localhost,1433'],
            status=SQLServer.OK,
        )


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_autodiscovery_exclude_db_service_checks(aggregator, dd_run_check, instance_autodiscovery):
    instance_autodiscovery['autodiscovery_include'] = ['master']
    instance_autodiscovery['autodiscovery_exclude'] = ['msdb']
    check = SQLServer(CHECK_NAME, {}, [instance_autodiscovery])

    dd_run_check(check)

    # assert no connection is created for an excluded database
    aggregator.assert_service_check(
        'sqlserver.database.can_connect',
        tags=['db:msdb', 'optional:tag1', 'sqlserver_host:localhost,1433'],
        status=SQLServer.OK,
        count=0,
    )
    aggregator.assert_service_check(
        'sqlserver.database.can_connect',
        tags=['db:master', 'optional:tag1', 'sqlserver_host:localhost,1433'],
        status=SQLServer.OK,
    )


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_no_autodiscovery_service_checks(aggregator, dd_run_check, init_config, instance_docker):
    sqlserver_check = SQLServer(CHECK_NAME, init_config, [instance_docker])
    dd_run_check(sqlserver_check)

    # assert no database service checks
    aggregator.assert_service_check('sqlserver.database.can_connect', count=0)


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_autodiscovery_perf_counters(aggregator, dd_run_check, instance_autodiscovery):
    instance_autodiscovery['autodiscovery_include'] = ['master', 'msdb']
    check = SQLServer(CHECK_NAME, {}, [instance_autodiscovery])
    dd_run_check(check)

    expected_metrics = [
        'sqlserver.database.backup_restore_throughput',
        'sqlserver.database.log_bytes_flushed',
        'sqlserver.database.log_flushes',
        'sqlserver.database.log_flush_wait',
        'sqlserver.database.transactions',
        'sqlserver.database.write_transactions',
        'sqlserver.database.active_transactions',
    ]
    master_tags = [
        'database:master',
        'optional:tag1',
    ]
    msdb_tags = [
        'database:msdb',
        'optional:tag1',
    ]
    base_tags = ['optional:tag1']
    for metric in expected_metrics:
        aggregator.assert_metric(metric, tags=master_tags)
        aggregator.assert_metric(metric, tags=msdb_tags)
        aggregator.assert_metric(metric, tags=base_tags)


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_autodiscovery_perf_counters_doesnt_duplicate_names_of_metrics_to_collect(dd_run_check, instance_autodiscovery):
    instance_autodiscovery['autodiscovery_include'] = ['master', 'msdb']
    check = SQLServer(CHECK_NAME, {}, [instance_autodiscovery])
    dd_run_check(check)

    for _cls, metric_names in check.instance_per_type_metrics.items():
        expected = list(set(metric_names))
        assert sorted(metric_names) == sorted(expected)


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_custom_queries(aggregator, dd_run_check, instance_docker):
    instance = copy(instance_docker)
    querya = copy(CUSTOM_QUERY_A)
    queryb = copy(CUSTOM_QUERY_B)
    instance['custom_queries'] = [querya, queryb]

    check = SQLServer(CHECK_NAME, {}, [instance])
    dd_run_check(check)
    tags = list(instance['tags'])

    for tag in ('a', 'b', 'c'):
        value = ord(tag)
        custom_tags = ['customtag:{}'.format(tag)]
        custom_tags.extend(tags)

        aggregator.assert_metric('sqlserver.num', value=value, tags=custom_tags + ['query:custom'])
        aggregator.assert_metric('sqlserver.num', value=value, tags=custom_tags + ['query:another_custom_one'])


@not_windows_ci
@pytest.mark.integration
@pytest.mark.usefixtures('dd_environment')
def test_load_static_information(aggregator, dd_run_check, instance_docker):
    instance = copy(instance_docker)
    check = SQLServer(CHECK_NAME, {}, [instance])
    dd_run_check(check)
    assert 'version' in check.static_info_cache, "missing version static information"
    assert check.static_info_cache['version'], "empty version in static information"


@windows_ci
@pytest.mark.integration
def test_check_windows_defaults(aggregator, dd_run_check, init_config, instance_sql2017_defaults):
    check = SQLServer(CHECK_NAME, init_config, [instance_sql2017_defaults])
    dd_run_check(check)

    aggregator.assert_metric_has_tag('sqlserver.db.commit_table_entries', 'db:master')

    for mname in EXPECTED_DEFAULT_METRICS + CUSTOM_METRICS:
        aggregator.assert_metric(mname)

    aggregator.assert_service_check('sqlserver.can_connect', status=SQLServer.OK)
    aggregator.assert_all_metrics_covered()
