"""Tests for the prompt pipeline module."""

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


class TestLatexProcessor:
    """Tests for LaTeX to speech conversion."""

    def test_inline_math(self):
        from backend.prompt_pipeline import LatexProcessor

        processor = LatexProcessor(speak_mode="math", verbosity="short")
        text = "The equation is $E = mc^2$"
        result, modified = processor.process(text)

        assert "E = mc to the power of 2" in result
        assert modified is True

    def test_fraction(self):
        from backend.prompt_pipeline import LatexProcessor

        processor = LatexProcessor(speak_mode="math", verbosity="short")
        text = "The fraction is $\\frac{a}{b}$"
        result, modified = processor.process(text)

        assert "a divided by b" in result
        assert modified is True

    def test_greek_letters(self):
        from backend.prompt_pipeline import LatexProcessor

        processor = LatexProcessor(speak_mode="math", verbosity="short")
        text = "Alpha is $\\alpha$ and Beta is $\\beta$"
        result, modified = processor.process(text)

        assert "alpha" in result.lower()
        assert "beta" in result.lower()
        assert modified is True

    def test_operators(self):
        from backend.prompt_pipeline import LatexProcessor

        processor = LatexProcessor(speak_mode="math", verbosity="short")
        text = "Less than or equal: $x \\leq y$"
        result, modified = processor.process(text)

        assert "less than or equal to" in result
        assert modified is True

    def test_literal_mode(self):
        from backend.prompt_pipeline import LatexProcessor

        processor = LatexProcessor(speak_mode="literal", verbosity="short")
        text = "The equation is $E = mc^2$"
        result, modified = processor.process(text)

        assert "E = mc^2" in result
        assert "[math:" in result
        assert modified is False

    def test_no_math(self):
        from backend.prompt_pipeline import LatexProcessor

        processor = LatexProcessor(speak_mode="math", verbosity="short")
        text = "This is plain text without any math."
        result, modified = processor.process(text)

        assert text == result
        assert modified is False

    def test_detailed_verbosity(self):
        from backend.prompt_pipeline import LatexProcessor

        processor = LatexProcessor(speak_mode="math", verbosity="detailed")
        text = "$$E = mc^2$$"
        result, modified = processor.process(text)

        assert "Equation:" in result
        assert modified is True


class TestPromptPipeline:
    """Tests for the unified prompt pipeline."""

    def test_default_mode(self):
        from backend.prompt_pipeline import PromptPipeline

        pipeline = PromptPipeline()
        result = pipeline.compose(
            text="Hello world",
            mode="default",
        )

        assert result.preprocessed_text == "Hello world"
        assert result.mode_persona is not None
        assert "clear, professional speaker" in result.mode_persona

    def test_study_mode(self):
        from backend.prompt_pipeline import PromptPipeline

        pipeline = PromptPipeline()
        result = pipeline.compose(
            text="The derivative of x squared is 2x.",
            mode="study",
        )

        assert "pedagogical tutor" in result.mode_persona
        assert result.latex_processed is True or "2x" in result.preprocessed_text

    def test_article_mode(self):
        from backend.prompt_pipeline import PromptPipeline

        pipeline = PromptPipeline()
        result = pipeline.compose(
            text="Once upon a time...",
            mode="article",
        )

        assert "skilled narrator" in result.mode_persona

    def test_tone_preset_resolution(self):
        from backend.prompt_pipeline import PromptPipeline

        pipeline = PromptPipeline()
        result = pipeline.compose(
            text="Test text",
            mode="default",
            tone_id="neutral",
        )

        assert (
            result.style_prompt is not None
            or result.debug_payload.get("tone_id") == "neutral"
        )

    def test_debug_payload_includes_all_inputs(self):
        from backend.prompt_pipeline import PromptPipeline

        pipeline = PromptPipeline(debug_mode=True)
        result = pipeline.compose(
            text="Test input text",
            mode="study",
            tone_id="excited",
            prompt_id="warm_confident",
            style="Custom style",
            voice_prompt="Custom voice prompt",
            voice_id="parler_en_neutral",
            auto_punctuate=True,
            latex_speak_mode="math",
            latex_verbosity="detailed",
            latex_literal=False,
            model_name="parler-tts/parler-tts-mini-v1.1",
        )

        debug = result.debug_payload
        assert debug["input_text_length"] == len("Test input text")
        assert debug["mode"] == "study"
        assert debug["tone_id"] == "excited"
        assert debug["prompt_id"] == "warm_confident"
        assert debug["user_style"] == "Custom style"
        assert debug["user_voice_prompt"] == "Custom voice prompt"
        assert debug["model_name"] == "parler-tts/parler-tts-mini-v1.1"
        assert debug["voice_id"] == "parler_en_neutral"

    def test_secrets_redacted(self):
        from backend.prompt_pipeline import PromptPipeline

        pipeline = PromptPipeline(debug_mode=True, hf_token="secret_token_12345")
        result = pipeline.compose(text="Test", mode="default")

        debug_dict = result.to_dict(redact_secrets=True)
        assert "***REDACTED***" in str(debug_dict)
        assert "secret_token_12345" not in str(debug_dict)

    def test_latex_settings_in_debug(self):
        from backend.prompt_pipeline import PromptPipeline

        pipeline = PromptPipeline()
        result = pipeline.compose(
            text="$a + b$",
            mode="default",
            latex_speak_mode="math",
            latex_verbosity="detailed",
            latex_literal=True,
        )

        assert result.latex_settings["speak_mode"] == "math"
        assert result.latex_settings["verbosity"] == "detailed"
        assert result.latex_settings["literal"] is True


class TestModes:
    """Tests for mode configurations."""

    def test_mode_configs_exist(self):
        from backend.prompt_pipeline import MODES, get_mode

        assert "default" in MODES
        assert "study" in MODES
        assert "article" in MODES

    def test_get_mode_default(self):
        from backend.prompt_pipeline import get_mode

        mode = get_mode("nonexistent")
        assert mode.id == "default"

    def test_study_mode_properties(self):
        from backend.prompt_pipeline import get_mode

        mode = get_mode("study")
        assert mode.id == "study"
        assert "pedagogical" in mode.persona_prompt.lower()
        assert mode.output_constraints.get("explanatory") is True

    def test_article_mode_properties(self):
        from backend.prompt_pipeline import get_mode

        mode = get_mode("article")
        assert mode.id == "article"
        assert "narrator" in mode.persona_prompt.lower()
        assert mode.output_constraints.get("structure") == "narrative"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
