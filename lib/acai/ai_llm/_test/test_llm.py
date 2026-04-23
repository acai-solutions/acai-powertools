import unittest

from acai.ai_llm.application import generate_prompt_evaluation_report
from acai.ai_llm.domain.content_block import ContentBlock, ContentType
from acai.ai_llm.domain.exceptions import (
    ConfigurationError,
    LlmError,
    ModelInvocationError,
    TextTooLongError,
)
from acai.ai_llm.domain.llm_config import LlmConfig
from acai.ai_llm.ports import LlmPort


# ---------------------------------------------------------------------------
# LlmConfig
# ---------------------------------------------------------------------------
class TestLlmConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = LlmConfig()
        self.assertEqual(cfg.max_text_length, 200_000)
        self.assertEqual(cfg.max_tokens, 4096)
        self.assertAlmostEqual(cfg.temperature, 0.7)
        self.assertEqual(cfg.retry_attempts, 3)
        self.assertEqual(cfg.timeout_seconds, 60)

    def test_custom_values(self):
        cfg = LlmConfig(max_text_length=1000, max_tokens=512, temperature=0.2)
        self.assertEqual(cfg.max_text_length, 1000)
        self.assertEqual(cfg.max_tokens, 512)
        self.assertAlmostEqual(cfg.temperature, 0.2)

    def test_zero_max_text_length_raises(self):
        with self.assertRaises(ConfigurationError):
            LlmConfig(max_text_length=0)

    def test_negative_max_text_length_raises(self):
        with self.assertRaises(ConfigurationError):
            LlmConfig(max_text_length=-1)

    def test_zero_max_tokens_raises(self):
        with self.assertRaises(ConfigurationError):
            LlmConfig(max_tokens=0)

    def test_negative_max_tokens_raises(self):
        with self.assertRaises(ConfigurationError):
            LlmConfig(max_tokens=-100)

    def test_temperature_below_zero_raises(self):
        with self.assertRaises(ConfigurationError):
            LlmConfig(temperature=-0.1)

    def test_temperature_above_one_raises(self):
        with self.assertRaises(ConfigurationError):
            LlmConfig(temperature=1.1)

    def test_temperature_boundary_zero(self):
        cfg = LlmConfig(temperature=0.0)
        self.assertAlmostEqual(cfg.temperature, 0.0)

    def test_temperature_boundary_one(self):
        cfg = LlmConfig(temperature=1.0)
        self.assertAlmostEqual(cfg.temperature, 1.0)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------
class TestExceptionHierarchy(unittest.TestCase):
    def test_llm_error_is_base(self):
        self.assertTrue(issubclass(ModelInvocationError, LlmError))
        self.assertTrue(issubclass(TextTooLongError, LlmError))
        self.assertTrue(issubclass(ConfigurationError, LlmError))

    def test_llm_error_is_exception(self):
        self.assertTrue(issubclass(LlmError, Exception))
        self.assertTrue(issubclass(ModelInvocationError, LlmError))


# ---------------------------------------------------------------------------
# LlmPort (ABC)
# ---------------------------------------------------------------------------
class TestLlmPort(unittest.TestCase):
    def test_abc_subclass_is_instance(self):
        class FakeLlm(LlmPort):
            def get_response(
                self,
                prompt,
                system_prompt=None,
                temperature=None,
                max_tokens=None,
                content_blocks=None,
            ):
                return {"response": "hi", "usage": {}, "model": "fake"}

        self.assertIsInstance(FakeLlm(), LlmPort)

    def test_non_subclass_not_instance(self):
        class NotAnLlm:
            pass

        self.assertNotIsInstance(NotAnLlm(), LlmPort)


# ---------------------------------------------------------------------------
# Prompt evaluation report
# ---------------------------------------------------------------------------
class TestPromptEvaluationReport(unittest.TestCase):
    def _make_result(self, scenario, score, output="out", reasoning="reason"):
        return {
            "test_case": {
                "scenario": scenario,
                "prompt_inputs": {"question": "What is X?"},
                "solution_criteria": ["criterion A", "criterion B"],
            },
            "score": score,
            "output": output,
            "reasoning": reasoning,
        }

    def test_html_contains_header(self):
        html = generate_prompt_evaluation_report([self._make_result("s1", 8)])
        self.assertIn("Prompt Evaluation Report", html)

    def test_html_contains_scenario(self):
        html = generate_prompt_evaluation_report([self._make_result("my_scenario", 5)])
        self.assertIn("my_scenario", html)

    def test_total_tests(self):
        results = [self._make_result(f"s{i}", i + 3) for i in range(4)]
        html = generate_prompt_evaluation_report(results)
        # stat-value div should contain "4"
        self.assertIn(">4<", html)

    def test_pass_rate_calculation(self):
        # 2 out of 4 tests with score >= 7
        results = [
            self._make_result("s1", 9),
            self._make_result("s2", 7),
            self._make_result("s3", 5),
            self._make_result("s4", 3),
        ]
        html = generate_prompt_evaluation_report(results)
        self.assertIn("50.0%", html)

    def test_score_css_classes(self):
        html_high = generate_prompt_evaluation_report([self._make_result("h", 9)])
        self.assertIn("score-high", html_high)

        html_low = generate_prompt_evaluation_report([self._make_result("l", 3)])
        self.assertIn("score-low", html_low)

        html_mid = generate_prompt_evaluation_report([self._make_result("m", 6)])
        self.assertIn("score-medium", html_mid)

    def test_empty_results(self):
        html = generate_prompt_evaluation_report([])
        self.assertIn("Prompt Evaluation Report", html)
        self.assertIn(">0<", html)

    def test_html_is_valid_structure(self):
        html = generate_prompt_evaluation_report([self._make_result("s", 5)])
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)

    def test_criteria_listed(self):
        html = generate_prompt_evaluation_report([self._make_result("s", 5)])
        self.assertIn("criterion A", html)
        self.assertIn("criterion B", html)


# ---------------------------------------------------------------------------
# Factory (smoke test with unknown provider)
# ---------------------------------------------------------------------------
class TestCreateLlmFactory(unittest.TestCase):
    def test_unknown_provider_raises(self):
        from acai.ai_llm import create_llm

        class _Logger:
            def info(self, *a, **k):
                pass

            def debug(self, *a, **k):
                pass

            def warning(self, *a, **k):
                pass

            def error(self, *a, **k):
                pass

        with self.assertRaises(ConfigurationError):
            create_llm(_Logger(), provider="unknown_provider")


# ---------------------------------------------------------------------------
# ContentBlock value object
# ---------------------------------------------------------------------------
class TestContentBlock(unittest.TestCase):
    def test_text_block(self):
        block = ContentBlock.text("hello")
        self.assertEqual(block.content_type, ContentType.TEXT)
        self.assertEqual(block.data, "hello")
        self.assertIsNone(block.media_type)

    def test_image_block(self):
        block = ContentBlock.image("abc123", "image/png")
        self.assertEqual(block.content_type, ContentType.IMAGE)
        self.assertEqual(block.data, "abc123")
        self.assertEqual(block.media_type, "image/png")

    def test_document_block(self):
        block = ContentBlock.document("pdf_data", "application/pdf", "doc.pdf")
        self.assertEqual(block.content_type, ContentType.DOCUMENT)
        self.assertEqual(block.data, "pdf_data")
        self.assertEqual(block.media_type, "application/pdf")
        self.assertEqual(block.filename, "doc.pdf")

    def test_empty_data_raises(self):
        with self.assertRaises(ValueError):
            ContentBlock.text("")

    def test_image_without_media_type_raises(self):
        with self.assertRaises(ValueError):
            ContentBlock(content_type=ContentType.IMAGE, data="abc")

    def test_document_without_media_type_raises(self):
        with self.assertRaises(ValueError):
            ContentBlock(content_type=ContentType.DOCUMENT, data="abc")

    def test_frozen(self):
        block = ContentBlock.text("hello")
        with self.assertRaises(AttributeError):
            block.data = "other"


# ---------------------------------------------------------------------------
# Adapter _build_content_blocks (unit, no API call)
# ---------------------------------------------------------------------------
class TestAnthropicBuildContentBlocks(unittest.TestCase):
    def test_plain_text_without_blocks(self):
        from acai.ai_llm.adapters.outbound.anthropic_claude_adapter import (
            AnthropicClaudeAdapter,
        )

        result = AnthropicClaudeAdapter._build_content_blocks("hello", None)
        self.assertEqual(result, "hello")

    def test_with_pdf_block(self):
        from acai.ai_llm.adapters.outbound.anthropic_claude_adapter import (
            AnthropicClaudeAdapter,
        )

        blocks = [ContentBlock.document("PDFDATA", "application/pdf", "f.pdf")]
        result = AnthropicClaudeAdapter._build_content_blocks("summarize", blocks)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "document")
        self.assertEqual(result[0]["source"]["media_type"], "application/pdf")
        self.assertEqual(result[1], {"type": "text", "text": "summarize"})

    def test_with_image_block(self):
        from acai.ai_llm.adapters.outbound.anthropic_claude_adapter import (
            AnthropicClaudeAdapter,
        )

        blocks = [ContentBlock.image("IMGDATA", "image/png")]
        result = AnthropicClaudeAdapter._build_content_blocks("describe", blocks)

        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["type"], "image")
        self.assertEqual(result[0]["source"]["data"], "IMGDATA")


class TestBedrockBuildContentBlocks(unittest.TestCase):
    def test_plain_text_without_blocks(self):
        from acai.ai_llm.adapters.outbound.bedrock_claude_adapter import (
            BedrockClaudeAdapter,
        )

        result = BedrockClaudeAdapter._build_content_blocks("hello", None)
        self.assertEqual(result, "hello")

    def test_with_pdf_block(self):
        from acai.ai_llm.adapters.outbound.bedrock_claude_adapter import (
            BedrockClaudeAdapter,
        )

        blocks = [ContentBlock.document("PDFDATA", "application/pdf")]
        result = BedrockClaudeAdapter._build_content_blocks("summarize", blocks)

        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["type"], "document")
        self.assertEqual(result[1], {"type": "text", "text": "summarize"})


class TestOpenAIBuildContentBlocks(unittest.TestCase):
    def test_plain_text_without_blocks(self):
        from acai.ai_llm.adapters.outbound.openai_adapter import OpenAIAdapter

        result = OpenAIAdapter._build_content_blocks("hello", None)
        self.assertEqual(result, "hello")

    def test_with_pdf_block(self):
        from acai.ai_llm.adapters.outbound.openai_adapter import OpenAIAdapter

        blocks = [ContentBlock.document("PDFDATA", "application/pdf", "f.pdf")]
        result = OpenAIAdapter._build_content_blocks("summarize", blocks)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "file")
        self.assertIn("file_data", result[0]["file"])
        self.assertEqual(result[0]["file"]["filename"], "f.pdf")
        self.assertEqual(result[1], {"type": "text", "text": "summarize"})

    def test_with_image_block(self):
        from acai.ai_llm.adapters.outbound.openai_adapter import OpenAIAdapter

        blocks = [ContentBlock.image("IMGDATA", "image/jpeg")]
        result = OpenAIAdapter._build_content_blocks("describe", blocks)

        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["type"], "image_url")
        self.assertIn("data:image/jpeg;base64,IMGDATA", result[0]["image_url"]["url"])


if __name__ == "__main__":
    unittest.main()
