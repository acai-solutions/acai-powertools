"""Tests for ``acai.logging`` — Logger domain service, context, decorator, LogLevel."""

import io
import logging
from unittest.mock import MagicMock

import pytest
from acai.logging import LoggerContext, LogLevel, create_logger
from acai.logging.domain.logger import Logger
from acai.logging.ports import LoggerPort

# ── Context stack ─────────────────────────────────────────────────────


class TestLoggerContextStack:
    def test_push_pop_context(self):
        logger = create_logger()
        logger.push_context({"request_id": "abc"})
        assert logger.get_current_context() == {"request_id": "abc"}  # nosec B101
        popped = logger.pop_context()
        assert popped == {"request_id": "abc"}  # nosec B101
        assert logger.get_current_context() == {}  # nosec B101

    def test_nested_context(self):
        logger = create_logger()
        logger.push_context({"a": 1})
        logger.push_context({"b": 2})
        merged = logger.get_current_context()
        assert merged == {"a": 1, "b": 2}  # nosec B101
        logger.pop_context()
        assert logger.get_current_context() == {"a": 1}  # nosec B101

    def test_pop_empty_returns_none(self):
        logger = create_logger()
        assert logger.pop_context() is None  # nosec B101

    def test_clear_context(self):
        logger = create_logger()
        logger.push_context({"a": 1})
        logger.push_context({"b": 2})
        logger.clear_context()
        assert logger.get_current_context() == {}  # nosec B101


# ── LoggerContext manager ─────────────────────────────────────────────


class TestLoggerContextManager:
    def test_context_present_inside(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)
        with LoggerContext(logger, {"batch": "b-7"}):
            logger.info("inside")
            kwargs = mock.log.call_args[1]
            assert kwargs.get("batch") == "b-7"  # nosec B101

    def test_context_absent_after_exit(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)
        with LoggerContext(logger, {"batch": "b-7"}):
            logger.info("inside")
        mock.reset_mock()
        logger.info("outside")
        kwargs = mock.log.call_args[1]
        assert "batch" not in kwargs  # nosec B101

    def test_cleanup_on_exception(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)
        with pytest.raises(ValueError, match="boom"):
            with LoggerContext(logger, {"err_ctx": True}):
                raise ValueError("boom")
        assert logger.get_current_context() == {}  # nosec B101

    def test_nested_contexts(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)
        with LoggerContext(logger, {"outer": 1}):
            with LoggerContext(logger, {"inner": 2}):
                assert logger.get_current_context() == {
                    "outer": 1,
                    "inner": 2,
                }  # nosec B101
            assert logger.get_current_context() == {"outer": 1}  # nosec B101
        assert logger.get_current_context() == {}  # nosec B101


# ── Lambda context decorator ─────────────────────────────────────────


class _FakeLambdaContext:
    aws_request_id = "req-abc-123"
    function_name = "my-func"
    function_version = "$LATEST"
    memory_limit_in_mb = 128
    log_group_name = "/aws/lambda/my-func"
    log_stream_name = "2026/03/23/[$LATEST]xyz"

    @staticmethod
    def get_remaining_time_in_millis():
        return 300_000


class TestLambdaDecorator:
    def test_request_id_injected(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)

        @logger.inject_lambda_context(include_event=True, include_context=True)
        def handler(event, context):
            logger.info("inside")
            return {"ok": True}

        handler({"action": "embed"}, _FakeLambdaContext())
        all_kwargs = [c[1] for c in mock.log.call_args_list]
        assert any(
            kw.get("aws_request_id") == "req-abc-123" for kw in all_kwargs
        )  # nosec B101

    def test_cold_start_tracked(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)

        @logger.inject_lambda_context(include_cold_start=True)
        def handler(event, context):
            logger.info("call")
            return "ok"

        # First call: cold_start=True
        handler({}, _FakeLambdaContext())
        all_kwargs = [c[1] for c in mock.log.call_args_list]
        assert any(kw.get("cold_start") is True for kw in all_kwargs)  # nosec B101

        # Second call: cold_start=False
        mock.reset_mock()
        handler({}, _FakeLambdaContext())
        all_kwargs2 = [c[1] for c in mock.log.call_args_list]
        assert any(kw.get("cold_start") is False for kw in all_kwargs2)  # nosec B101

    def test_handler_return_value_preserved(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)

        @logger.inject_lambda_context()
        def handler(event, context):
            return {"status": "ok"}

        result = handler({}, _FakeLambdaContext())
        assert result == {"status": "ok"}  # nosec B101

    def test_handler_exception_reraised(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)

        @logger.inject_lambda_context(log_exceptions=True)
        def handler(event, context):
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            handler({}, _FakeLambdaContext())

    def test_context_cleaned_after_invocation(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)

        @logger.inject_lambda_context(include_context=True)
        def handler(event, context):
            return "ok"

        handler({}, _FakeLambdaContext())
        assert logger.get_current_context() == {}  # nosec B101

    def test_no_parentheses_form(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)

        @logger.inject_lambda_context
        def handler(event, context):
            logger.info("no-parens")
            return {"ok": True}

        result = handler({"action": "test"}, _FakeLambdaContext())
        assert result == {"ok": True}  # nosec B101
        assert mock.log.call_count >= 1  # nosec B101


# ── Error resilience ──────────────────────────────────────────────────


class TestErrorResilience:
    def test_adapter_exception_does_not_crash(self):
        mock = MagicMock(spec=LoggerPort)
        mock.log.side_effect = RuntimeError("adapter exploded")
        logger = Logger(mock)
        # Should not raise
        logger.info("this should not crash")

    def test_fallback_warning_logged(self):
        mock = MagicMock(spec=LoggerPort)
        mock.log.side_effect = RuntimeError("adapter exploded")
        logger = Logger(mock)

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logging.Formatter("%(message)s"))
        domain_logger = logging.getLogger("acai.logging.domain.logger")
        domain_logger.addHandler(handler)
        domain_logger.setLevel(logging.DEBUG)
        try:
            logger.info("trigger fallback")
        finally:
            domain_logger.removeHandler(handler)

        assert "Logger failed" in buf.getvalue()  # nosec B101


# ── LogLevel conversion ──────────────────────────────────────────────


class TestLogLevelConversion:
    def test_enum_to_native(self):
        assert LogLevel.to_native(LogLevel.DEBUG) == 10  # nosec B101
        assert LogLevel.to_native(LogLevel.CRITICAL) == 50  # nosec B101

    def test_string_to_native(self):
        assert LogLevel.to_native("debug") == 10  # nosec B101
        assert LogLevel.to_native("WARNING") == 30  # nosec B101

    def test_int_passthrough(self):
        assert LogLevel.to_native(25) == 25  # nosec B101

    def test_unknown_string_defaults_to_info(self):
        assert LogLevel.to_native("nonexistent") == 20  # nosec B101

    def test_level_name(self):
        assert LogLevel.level_name(10) == "DEBUG"  # nosec B101
        assert LogLevel.level_name(40) == "ERROR"  # nosec B101
        assert LogLevel.level_name(99).startswith("LVL")  # nosec B101


# ── Convenience methods ───────────────────────────────────────────────


class TestLoggerConvenienceMethods:
    def test_all_levels_delegate_to_log(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)
        logger.debug("d")
        logger.info("i")
        logger.warning("w")
        logger.error("e")
        logger.critical("c")
        assert mock.log.call_count == 5  # nosec B101

    def test_kwargs_forwarded(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)
        logger.info("msg", key="val", num=42)
        _, kwargs = mock.log.call_args
        assert kwargs["key"] == "val"  # nosec B101
        assert kwargs["num"] == 42  # nosec B101

    def test_context_merged_with_kwargs(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)
        logger.push_context({"request_id": "r-1"})
        logger.info("msg", extra="e")
        _, kwargs = mock.log.call_args
        assert kwargs["request_id"] == "r-1"  # nosec B101
        assert kwargs["extra"] == "e"  # nosec B101
        logger.clear_context()

    def test_kwargs_override_context(self):
        mock = MagicMock(spec=LoggerPort)
        logger = Logger(mock)
        logger.push_context({"key": "ctx"})
        logger.info("msg", key="override")
        _, kwargs = mock.log.call_args
        assert kwargs["key"] == "override"  # nosec B101
        logger.clear_context()
