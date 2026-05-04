__all__ = [
    "ConsoleLogger",
    "AwsLambdaPtLogger",
    "CloudWatchLogger",
    "FileLogger",
    "AwsOpenSearchLogger",
    "ElasticsearchLogger",
    "GrafanaCloudLogger",
    "LogzioLogger",
    "LokiLogger",
    "MultiLogger",
]

_LAZY = {
    "ConsoleLogger": ".console_logger",
    "FileLogger": ".file_logger",
    "AwsLambdaPtLogger": ".aws_lambda_pt_logger",
    "CloudWatchLogger": ".cloudwatch_logger",
    "AwsOpenSearchLogger": ".aws_opensearch_logger",
    "ElasticsearchLogger": ".elasticsearch_logger",
    "GrafanaCloudLogger": ".grafana_cloud_logger",
    "LogzioLogger": ".logzio_logger",
    "LokiLogger": ".loki_logger",
    "MultiLogger": ".multi_logger",
}


def __getattr__(name: str):
    module_path = _LAZY.get(name)
    if module_path is not None:
        import importlib

        module = importlib.import_module(module_path, __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
