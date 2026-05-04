__all__ = [
    "ConsoleLogger",
    "AwsLambdaPtLogger",
    "CloudWatchLogger",
    "FileLogger",
    "AwsOpenSearchLogger",
    "ElasticsearchLogger",
    "LogzioLogger",
    "LokiLogger",
    "MultiLogger",
]

_LAZY = {
    "ConsoleLogger": ".outbound.console_logger",
    "FileLogger": ".outbound.file_logger",
    "AwsLambdaPtLogger": ".outbound.aws_lambda_pt_logger",
    "CloudWatchLogger": ".outbound.cloudwatch_logger",
    "AwsOpenSearchLogger": ".outbound.aws_opensearch_logger",
    "ElasticsearchLogger": ".outbound.elasticsearch_logger",
    "LogzioLogger": ".outbound.logzio_logger",
    "LokiLogger": ".outbound.loki_logger",
    "MultiLogger": ".outbound.multi_logger",
}


def __getattr__(name: str):
    module_path = _LAZY.get(name)
    if module_path is not None:
        import importlib

        module = importlib.import_module(module_path, __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
