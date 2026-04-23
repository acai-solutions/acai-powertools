from .console_logger import ConsoleLogger
from .file_logger import FileLogger

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
    "AwsLambdaPtLogger": ".aws_lambda_pt_logger",
    "CloudWatchLogger": ".cloudwatch_logger",
    "AwsOpenSearchLogger": ".aws_opensearch_logger",
    "ElasticsearchLogger": ".elasticsearch_logger",
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
