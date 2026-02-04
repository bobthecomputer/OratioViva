"""Unified Prompt Pipeline for OratioViva"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class ModeConfig:
    id: str
    name: str
    description: str
    persona_prompt: str
    preprocessing_rules: Dict[str, Any] = field(default_factory=dict)
    output_constraints: Dict[str, Any] = field(default_factory=dict)


STUDY_MODE = ModeConfig(
    id="study",
    name="Study Mode",
    description="Pedagogical voice with structured explanations",
    persona_prompt="You are a patient, pedagogical tutor helping a learner understand complex material.",
    preprocessing_rules={
        "expand_abbreviations": True,
        "spell_out_acronyms": True,
        "pace": "slower",
        "equation_verbosity": "detailed",
    },
    output_constraints={
        "verbosity": "detailed",
        "explanatory": True,
        "structure": "tutorial",
    },
)

ARTICLE_MODE = ModeConfig(
    id="article",
    name="Article Mode",
    description="Clean narrative voice for smooth listening",
    persona_prompt="You are a skilled narrator delivering content in a smooth, engaging flow.",
    preprocessing_rules={
        "expand_abbreviations": False,
        "pace": "normal",
        "equation_verbosity": "short",
    },
    output_constraints={
        "verbosity": "moderate",
        "explanatory": False,
        "structure": "narrative",
    },
)

DEFAULT_MODE = ModeConfig(
    id="default",
    name="Default Mode",
    description="Standard delivery with natural prosody",
    persona_prompt="You are a clear, professional speaker delivering content naturally.",
    preprocessing_rules={
        "pace": "normal",
        "equation_verbosity": "short",
    },
    output_constraints={
        "verbosity": "normal",
        "structure": "standard",
    },
)

MODES: Dict[str, ModeConfig] = {
    "default": DEFAULT_MODE,
    "study": STUDY_MODE,
    "article": ARTICLE_MODE,
}


def get_mode(mode_id: str) -> ModeConfig:
    return MODES.get(mode_id, DEFAULT_MODE)


@dataclass
class ComposedPrompt:
    preprocessed_text: str
    style_prompt: Optional[str]
    voice_prompt: Optional[str]
    combined_tts_prompt: Optional[str]
    system_prompt: str
    mode_persona: str
    latex_processed: bool
    latex_settings: Dict[str, Any]
    debug_payload: Dict[str, Any]

    def to_dict(self, redact_secrets: bool = True) -> Dict[str, Any]:
        data = {
            "preprocessed_text": self.preprocessed_text,
            "style_prompt": self.style_prompt,
            "voice_prompt": self.voice_prompt,
            "combined_tts_prompt": self.combined_tts_prompt,
            "system_prompt": self.system_prompt,
            "mode_persona": self.mode_persona,
            "latex_processed": self.latex_processed,
            "latex_settings": self.latex_settings,
        }
        if redact_secrets:
            data["debug_payload"] = self._redact_secrets(self.debug_payload)
        else:
            data["debug_payload"] = self.debug_payload
        return data

    @staticmethod
    def _redact_secrets(payload: Dict[str, Any]) -> Dict[str, Any]:
        secrets = {"hf_token", "api_key", "password", "secret", "token"}
        redacted = {}
        for key, value in payload.items():
            if any(secret in key.lower() for secret in secrets):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = ComposedPrompt._redact_secrets(value)
            else:
                redacted[key] = value
        return redacted


class LatexProcessor:
    GREEK_LETTERS = {
        "alpha": "alpha",
        "beta": "beta",
        "gamma": "gamma",
        "delta": "delta",
        "epsilon": "epsilon",
        "zeta": "zeta",
        "eta": "eta",
        "theta": "theta",
        "iota": "iota",
        "kappa": "kappa",
        "lambda": "lambda",
        "mu": "mu",
        "nu": "nu",
        "xi": "xi",
        "pi": "pi",
        "rho": "rho",
        "sigma": "sigma",
        "tau": "tau",
        "upsilon": "upsilon",
        "phi": "phi",
        "chi": "chi",
        "psi": "psi",
        "omega": "omega",
        "Gamma": "Gamma",
        "Delta": "Delta",
        "Theta": "Theta",
        "Lambda": "Lambda",
        "Pi": "Pi",
        "Sigma": "Sigma",
        "Phi": "Phi",
        "Omega": "Omega",
    }

    OPERATORS = {
        r"\cdot": "times",
        r"\times": "times",
        r"\div": "divided by",
        r"\pm": "plus or minus",
        r"\mp": "minus or plus",
        r"\leq": "less than or equal to",
        r"\geq": "greater than or equal to",
        r"\neq": "not equal to",
        r"\approx": "approximately",
        r"\equiv": "equivalent to",
        r"\infty": "infinity",
        r"\partial": "partial",
        r"\nabla": "nabla",
        r"\sum": "sum",
        r"\prod": "product",
        r"\int": "integral",
        r"\sqrt": "square root",
        r"\frac": "fraction",
    }

    def __init__(
        self,
        speak_mode: str = "math",
        verbosity: str = "short",
        literal_math: bool = False,
    ):
        self.speak_mode = speak_mode
        self.verbosity = verbosity
        self.literal_math = literal_math

    def process(self, text: str) -> Tuple[str, bool]:
        if self.literal_math:
            return text, False

        original = text
        text = self._process_display_math(text)
        text = self._process_inline_math(text)
        text = self._fix_spacing(text)

        if self.speak_mode == "literal":
            return text, False

        return text, text != original

    def _process_inline_math(self, text: str) -> str:
        pattern = r"\$([^\$]+)\$"

        def replace(match):
            math_content = match.group(1).strip()
            if self.speak_mode == "literal":
                return f"[math: {math_content}]"
            return self._speak_math(math_content)

        return re.sub(pattern, replace, text)

    def _process_display_math(self, text: str) -> str:
        patterns = [
            (r"\$\$([\s\S]+?)\$\$", True),
            (r"\\\((?:[^\(\)]|\([^)]*\))+\\\)", False),
        ]

        for pattern, is_display in patterns:
            text = re.sub(
                pattern,
                lambda m: self._speak_math(m.group(1), is_display=is_display),
                text,
            )

        return text

    def _speak_math(self, content: str, is_display: bool = False) -> str:
        result = content

        result = self._preprocess_math_content(result)

        result = re.sub(r"\\,", " ", result)
        result = re.sub(r"\\ ", " ", result)
        result = re.sub(r"\{", "", result)
        result = re.sub(r"\}", "", result)

        result = re.sub(r"\s+", " ", result).strip()

        if self.verbosity == "detailed" and is_display:
            result = f"Equation: {result}"

        return result

    def _preprocess_math_content(self, text: str) -> str:
        text = self._fix_integrals(text)
        text = self._fix_sums_products(text)
        text = self._fix_limits(text)
        text = self._fix_fractions(text)
        text = self._fix_roots(text)
        text = self._fix_operators(text)
        text = self._fix_greek(text)
        text = self._fix_functions(text)
        text = self._fix_text_commands(text)
        text = self._fix_subscripts_superscripts(text)
        text = self._fix_delimiters(text)
        return text

    def _fix_text_commands(self, text: str) -> str:
        text = re.sub(r"\\mathbf\{([A-Za-z])\}", r" bold \1", text)
        text = re.sub(r"\\mathbf\{([^}]+)\}", r" bold text \1", text)
        text = re.sub(r"\\mathrm\{([A-Za-z])\}", r" \1", text)
        text = re.sub(r"\\mathrm\{([^}]+)\}", r" \1", text)
        text = re.sub(r"\\mathit\{([A-Za-z])\}", r" \1", text)
        text = re.sub(r"\\mathit\{([^}]+)\}", r" \1", text)
        text = re.sub(r"\\mathsf\{([A-Za-z])\}", r" \1", text)
        text = re.sub(r"\\mathsf\{([^}]+)\}", r" \1", text)
        text = re.sub(r"\\texttt\{([A-Za-z])\}", r" \1", text)
        text = re.sub(r"\\texttt\{([^}]+)\}", r" \1", text)
        return text

    def _fix_delimiters(self, text: str) -> str:
        text = re.sub(r"\\,", " ", text)
        text = re.sub(r"\\ ", " ", text)
        text = re.sub(r"\{", "", text)
        text = re.sub(r"\}", "", text)
        return text

    def _fix_subscripts_superscripts(self, text: str) -> str:
        text = re.sub(r"_(\{[^{}]+\})", r" sub \1", text)
        text = re.sub(r"_([a-zA-Z0-9])(?![a-zA-Z0-9])", r" sub \1", text)
        text = re.sub(r"\^(\{[^{}]+\})", r" to the power of \1", text)
        text = re.sub(r"\^([a-zA-Z0-9])(?![a-zA-Z0-9])", r" to the power of \1", text)
        return text

    def _fix_integrals(self, text: str) -> str:
        pattern = r"\\int_\{([^}]+)\}\^\{([^}]+)\}"
        text = re.sub(pattern, r"integral from \1 to \2 of", text)
        pattern = r"\\int_([a-zA-Z0-9]+)\^\{([^}]+)\}"
        text = re.sub(pattern, r"integral from \1 to \2 of", text)
        pattern = r"\\int_\{([^}]+)\}\^([a-zA-Z0-9]+)"
        text = re.sub(pattern, r"integral from \1 to \2 of", text)
        pattern = r"\\int_([a-zA-Z0-9]+)\^([a-zA-Z0-9]+)"
        text = re.sub(pattern, r"integral from \1 to \2 of", text)
        pattern = r"\\int"
        text = re.sub(pattern, "integral of", text)
        return text

    def _fix_sums_products(self, text: str) -> str:
        pattern = r"\\sum_\{([^}]+)\}\^\{([^}]+)\}"
        text = re.sub(pattern, r"sum from \1 to \2 of", text)
        pattern = r"\\prod_\{([^}]+)\}\^\{([^}]+)\}"
        text = re.sub(pattern, r"product from \1 to \2 of", text)
        pattern = r"\\sum_\{([^}]+)\}"
        text = re.sub(pattern, r"sum over \1 of", text)
        pattern = r"\\prod_\{([^}]+)\}"
        text = re.sub(pattern, r"product over \1 of", text)
        pattern = r"\\sum"
        text = re.sub(pattern, "sum", text)
        pattern = r"\\prod"
        text = re.sub(pattern, "product", text)
        return text

    def _fix_limits(self, text: str) -> str:
        pattern = r"\\lim_\{([^}]+)\}\s*->\s*\{([^}]+)\}"
        text = re.sub(pattern, r"limit as \1 approaches \2 of", text)
        pattern = r"\\lim_\{([^}]+)\}"
        text = re.sub(pattern, r"limit as \1 of", text)
        return text

    def _fix_fractions(self, text: str) -> str:
        pattern = r"\\frac\{([^}]+)\}\{([^}]+)\}"
        text = re.sub(pattern, r" \1 divided by \2 ", text)
        return text

    def _fix_roots(self, text: str) -> str:
        pattern = r"\\sqrt\[([^\]]+)\]\{([^}]+)\}"
        text = re.sub(pattern, r" \2th root of \1", text)
        pattern = r"\\sqrt\{([^}]+)\}"
        text = re.sub(pattern, r" square root of \1", text)
        return text

    def _fix_operators(self, text: str) -> str:
        replacements = {
            r"\cdot": " times ",
            r"\times": " times ",
            r"\div": " divided by ",
            r"\pm": " plus or minus ",
            r"\mp": " minus or plus ",
            r"\leq": " less than or equal to ",
            r"\geq": " greater than or equal to ",
            r"\neq": " not equal to ",
            r"\approx": " approximately ",
            r"\equiv": " equivalent to ",
            r"\infty": " infinity ",
            r"\partial": " partial ",
            r"\nabla": " nabla ",
            r"\int": " integral ",
            r"\oint": " contour integral ",
            r"\iint": " double integral ",
            r"\iiint": " triple integral ",
            r"\differentialD": " d ",
            r"\mathrm{d}": " d ",
            r"\delta": " delta ",
            r"\Delta": " Delta ",
            r"\circ": " degrees ",
            r"\cdot": " times ",
        }
        for latex, spoken in replacements.items():
            text = text.replace(latex, spoken)
        return text

    def _fix_functions(self, text: str) -> str:
        replacements = {
            r"\sin": "SINE",
            r"\cos": "COSINE",
            r"\tan": "TANGENT",
            r"\log": "LOG",
            r"\ln": "NATURAL LOG",
            r"\exp": "EXP",
            r"\det": "DET",
            r"\deg": "DEG",
            r"\dim": "DIM",
            r"\max": "MAX",
            r"\min": "MIN",
            r"\arg": "ARG",
            r"\mod": "MOD",
            r"\sin^{-1}": "ARC SINE",
            r"\cos^{-1}": "ARC COSINE",
            r"\tan^{-1}": "ARC TANGENT",
        }
        for latex, spoken in replacements.items():
            text = text.replace(latex, spoken)
        return text

    def _fix_greek(self, text: str) -> str:
        for latex, spoken in self.GREEK_LETTERS.items():
            text = text.replace(f"\\{latex}", f" {spoken} ")
        return text

    def _fix_spacing(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.strip()


class PromptPipeline:
    def __init__(
        self,
        debug_mode: bool = False,
        hf_token: Optional[str] = None,
    ):
        self.debug_mode = debug_mode
        self.hf_token = hf_token

    def compose(
        self,
        text: str,
        mode: str = "default",
        tone_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
        style: Optional[str] = None,
        voice_prompt: Optional[str] = None,
        voice_id: Optional[str] = None,
        auto_punctuate: bool = False,
        latex_speak_mode: str = "math",
        latex_verbosity: str = "short",
        latex_literal: bool = False,
        model_name: Optional[str] = None,
    ) -> ComposedPrompt:
        mode_config = get_mode(mode)

        preprocessed_text = self._preprocess_text(text, auto_punctuate)

        latex_processor = LatexProcessor(
            speak_mode=latex_speak_mode,
            verbosity=latex_verbosity,
            literal_math=latex_literal,
        )
        processed_text, latex_processed = latex_processor.process(preprocessed_text)

        style_prompt, voice_prompt_resolved = self._resolve_presets(
            tone_id, prompt_id, style, voice_prompt, model_name
        )

        combined_tts = self._combine_tts_prompts(style_prompt, voice_prompt_resolved)

        system_prompt = self._build_system_prompt(mode_config, voice_id)
        mode_persona = mode_config.persona_prompt

        latex_settings = {
            "speak_mode": latex_speak_mode,
            "verbosity": latex_verbosity,
            "literal": latex_literal,
            "processed": latex_processed,
        }

        debug_payload = self._build_debug_payload(
            text=text,
            mode=mode,
            tone_id=tone_id,
            prompt_id=prompt_id,
            style=style,
            voice_prompt=voice_prompt,
            voice_prompt_resolved=voice_prompt_resolved,
            style_prompt=style_prompt,
            combined_tts=combined_tts,
            latex_settings=latex_settings,
            model_name=model_name,
            voice_id=voice_id,
            mode_config=mode_config,
        )

        return ComposedPrompt(
            preprocessed_text=processed_text,
            style_prompt=style_prompt,
            voice_prompt=voice_prompt_resolved,
            combined_tts_prompt=combined_tts,
            system_prompt=system_prompt,
            mode_persona=mode_persona,
            latex_processed=latex_processed,
            latex_settings=latex_settings,
            debug_payload=debug_payload,
        )

    def _preprocess_text(self, text: str, auto_punctuate: bool) -> str:
        result = text

        if auto_punctuate:
            from backend.main import auto_punctuate_text

            result = auto_punctuate_text(result, None)

        return result

    def _resolve_presets(
        self,
        tone_id: Optional[str],
        prompt_id: Optional[str],
        style: Optional[str],
        voice_prompt: Optional[str],
        model_name: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        final_style = style
        final_voice_prompt = voice_prompt

        from backend.main import (
            load_presets,
            DEFAULT_TONE_PRESETS,
            DEFAULT_PROMPT_PRESETS,
        )

        presets = load_presets()
        tones = presets.get("tones", {})
        prompts = presets.get("prompts", {})

        if tone_id:
            default_tone_ids = {p.id for p in DEFAULT_TONE_PRESETS}
            if tone_id in default_tone_ids:
                for p in DEFAULT_TONE_PRESETS:
                    if p.id == tone_id:
                        tone_preset = p.model_dump()
                        break
            elif tone_id in tones:
                tone_preset = tones[tone_id]
            else:
                tone_preset = None

            if tone_preset:
                overrides = tone_preset.get("overrides", {})
                if model_name and model_name in overrides:
                    override = overrides[model_name]
                    if override:
                        if override.get("style") and not final_style:
                            final_style = override["style"]
                        if override.get("voice_prompt") and not final_voice_prompt:
                            final_voice_prompt = override["voice_prompt"]
                else:
                    if tone_preset.get("style") and not final_style:
                        final_style = tone_preset["style"]
                    if tone_preset.get("voice_prompt") and not final_voice_prompt:
                        final_voice_prompt = tone_preset["voice_prompt"]

        if prompt_id:
            default_prompt_ids = {p.id for p in DEFAULT_PROMPT_PRESETS}
            if prompt_id in default_prompt_ids:
                for p in DEFAULT_PROMPT_PRESETS:
                    if p.id == prompt_id:
                        prompt_preset = p.model_dump()
                        break
            elif prompt_id in prompts:
                prompt_preset = prompts[prompt_id]
            else:
                prompt_preset = None

            if prompt_preset:
                overrides = prompt_preset.get("overrides", {})
                if model_name and model_name in overrides:
                    override = overrides[model_name]
                    if override:
                        if override.get("style") and not final_style:
                            final_style = override["style"]
                        if override.get("voice_prompt") and not final_voice_prompt:
                            final_voice_prompt = override["voice_prompt"]
                else:
                    if prompt_preset.get("style") and not final_style:
                        final_style = prompt_preset["style"]
                    if prompt_preset.get("voice_prompt") and not final_voice_prompt:
                        final_voice_prompt = prompt_preset["voice_prompt"]

        return final_style, final_voice_prompt

    def _combine_tts_prompts(
        self, style_prompt: Optional[str], voice_prompt: Optional[str]
    ) -> Optional[str]:
        style_val = (style_prompt or "").strip()
        prompt_val = (voice_prompt or "").strip()

        if style_val and prompt_val:
            return f"{style_val}\n{prompt_val}"
        if style_val:
            return style_val
        if prompt_val:
            return prompt_val
        return None

    def _build_system_prompt(self, mode: ModeConfig, voice_id: Optional[str]) -> str:
        base = mode.persona_prompt
        if voice_id:
            return f"{base}\nVoice ID: {voice_id}"
        return base

    def _build_debug_payload(
        self,
        text: str,
        mode: str,
        tone_id: Optional[str],
        prompt_id: Optional[str],
        style: Optional[str],
        voice_prompt: Optional[str],
        voice_prompt_resolved: Optional[str],
        style_prompt: Optional[str],
        combined_tts: Optional[str],
        latex_settings: Dict[str, Any],
        model_name: Optional[str],
        voice_id: Optional[str],
        mode_config: Optional[ModeConfig] = None,
    ) -> Dict[str, Any]:
        return {
            "input_text_length": len(text),
            "mode": mode,
            "mode_name": mode_config.name if mode_config else mode,
            "tone_id": tone_id,
            "prompt_id": prompt_id,
            "user_style": style,
            "user_voice_prompt": voice_prompt,
            "resolved_style_prompt": style_prompt,
            "resolved_voice_prompt": voice_prompt_resolved,
            "combined_tts_prompt": combined_tts,
            "latex_settings": latex_settings,
            "model_name": model_name,
            "voice_id": voice_id,
            "hf_token_set": bool(self.hf_token),
        }
