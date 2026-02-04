"""Smart LaTeX to Text Processor - Cleans and optimizes LaTeX documents for TTS."""

import re
import sys
from pathlib import Path
from typing import Tuple

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from prompt_pipeline import LatexProcessor


def clean_latex_document(latex_text: str) -> str:
    """
    Clean a LaTeX document by removing LaTeX commands and keeping content.
    Returns speech-ready text.
    """
    text = latex_text

    text = _remove_latex_commands(text)
    text = _extract_section_content(text)
    text = _extract_item_content(text)
    text = _extract_tcolorbox_content(text)
    text = _clean_text_formatting(text)
    text = _clean_special_chars(text)
    text = _final_cleanup(text)

    return text.strip()


def _remove_latex_commands(text: str) -> str:
    """Remove LaTeX commands that aren't useful for speech."""

    patterns = [
        r"\\documentclass(\[[^\]]*\])?\{[^\}]+\}",
        r"\\usepackage(\[[^\]]*\])?\{[^\}]+\}",
        r"\\inputenc\{[^\}]+\}",
        r"\\fontenc\{[^\}]+\}",
        r"\\geometry\[[^\]]*\]",
        r"\\definecolor\{[^\}]+\}",
        r"\\colorlet\{[^\}]+\}",
        r"\\graphicspath\{[^\}]+\}",
        r"\\tcbuselibrary\{[^\}]+\}",
        r"\\newtcolorbox(\[[^\]]*\])?\{[^\}]+\}",
        r"\\titleformat\{[^\}]+\}",
        r"\\titlespacing\{[^\}]+\}",
        r"\\author\{[^\}]+\}",
        r"\\date\{[^\}]+\}",
        r"\\maketableofcontents",
        r"\\newpage",
        r"\\pagebreak",
        r"\\nopagebreak",
        r"\\hline",
        r"\\toprule",
        r"\\midrule",
        r"\\bottomrule",
        r"\\andadots",
        r"\\centering",
        r"\\raggedright",
        r"\\raggedleft",
        r"\\vspace\*?\[[^\]]*\]",
        r"\\hspace\*?\[[^\]]*\]",
        r"\\phantom\{[^\}]*\}",
        r"\\small",
        r"\\Large",
        r"\\large",
        r"\\ normalsize",
        r"\\footnote\[[^\]]*\](\{[^}]*\})?",
        r"\\footnote\{[^}]*\}",
        r"\\label\{[^\}]*\}",
        r"\\ref\{[^\}]*\}",
        r"\\cite\{[^\}]*\}",
        r"\\caption\{[^\}]*\}",
        r"\\bibliography\{[^\}]*\}",
        r"\\bibliographystyle\{[^\}]*\}",
        r"\\appendix",
        r"\\begin\{document\}",
        r"\\end\{document\}",
        r"\\begin\{titlepage\}",
        r"\\end\{titlepage\}",
        r"\\begin\{abstract\}",
        r"\\end\{abstract\}",
        r"\\begin\{figure\}[^\}]*\}",
        r"\\end\{figure\}",
        r"\\begin\{table\}[^\}]*\}",
        r"\\end\{table\}",
        r"\\begin\{center\}",
        r"\\end\{center\}",
        r"\\begin\{flushleft\}",
        r"\\end\{flushleft\}",
        r"\\begin\{flushright\}",
        r"\\end\{flushright\}",
        r"\\begin\{minipage\}[^\}]*\}",
        r"\\end\{minipage\}",
        r"\\begin\{tabular\}[^\}]*\}",
        r"\\end\{tabular\}",
        r"\\begin\{matrix\}(\[[^\]]*\])?\{[^\}]*\}",
        r"\\end\{matrix\}",
        r"\\begin\{bmatrix\}(\[[^\]]*\])?\{[^\}]*\}",
        r"\\end\{bmatrix\}",
        r"\\begin\{pmatrix\}(\[[^\]]*\])?\{[^\}]*\}",
        r"\\end\{pmatrix\}",
        r"\\begin\{cases\}(\[[^\]]*\])?\{[^\}]*\}",
        r"\\end\{cases\}",
        r"\\begin\{align\*?\}(\[[^\]]*\])?",
        r"\\end\{align\*?\}",
        r"\\begin\{equation\*?\}(\[[^\]]*\])?",
        r"\\end\{equation\*?\}",
        r"\\begin\{gather\*?\}(\[[^\]]*\])?",
        r"\\end\{gather\*?\}",
        r"\\begin\{multiline\*?\}(\[[^\]]*\])?",
        r"\\end\{multiline\*?\}",
        r"\\begin\{split\}(\[[^\]]*\])?",
        r"\\end\{split\}",
        r"\\begin\{comment\}",
        r"\\end\{comment\}",
        r"\\begin\{proof\}",
        r"\\end\{proof\}",
        r"\\begin\{remark\}",
        r"\\end\{remark\}",
        r"\\begin\{note\}",
        r"\\end\{note\}",
        r"\\begin\{warning\}",
        r"\\end\{warning\}",
        r"\\begin\{caution\}",
        r"\\end\{caution\}",
        r"\\begin\{important\}",
        r"\\end\{important\}",
        r"\\begin\{tip\}",
        r"\\end\{tip\}",
        r"\\item\[[^\]]*\]",
    ]

    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE | re.DOTALL)

    return text


def _extract_section_content(text: str) -> str:
    """Convert section commands to readable headings."""
    text = re.sub(r"\\section\*?\{([^\}]+)\}", r"\n\n=== \1 ===\n", text)
    text = re.sub(r"\\subsection\*?\{([^\}]+)\}", r"\n\n== \1 ==\n", text)
    text = re.sub(r"\\subsubsection\*?\{([^\}]+)\}", r"\n\n* \1 *\n", text)
    text = re.sub(r"\\paragraph\*?\{([^\}]+)\}", r"\n\n\1: ", text)
    return text


def _extract_item_content(text: str) -> str:
    """Convert itemize/enumerate to readable bullet points."""
    text = re.sub(r"\\begin\{itemize\}", "\n", text)
    text = re.sub(r"\\end\{itemize\}", "\n", text)
    text = re.sub(r"\\begin\{enumerate\}", "\n", text)
    text = re.sub(r"\\end\{enumerate\}", "\n", text)
    text = re.sub(r"\\begin\{description\}", "\n", text)
    text = re.sub(r"\\end\{description\}", "\n", text)
    text = re.sub(r"\\item\s+", "\n- ", text)
    return text


def _extract_tcolorbox_content(text: str) -> str:
    """Extract content from tcolorbox environments."""
    text = re.sub(
        r"\\begin\{masterformula\}(?:\[([^\]]*)\])?\{([^\}]+)\}",
        r"\n[Important Formula: \2]\n",
        text,
    )
    text = re.sub(r"\\end\{masterformula\}", "\n[/Important Formula]\n", text)
    text = re.sub(
        r"\\begin\{explanation\}(?:\[([^\]]*)\])?", r"\n[Explanation]\n", text
    )
    text = re.sub(r"\\end\{explanation\}", "\n[/Explanation]\n", text)
    text = re.sub(
        r"\\begin\{watchout\}(?:\[([^\]]*)\])?", r"\n[Warning / Important]\n", text
    )
    text = re.sub(r"\\end\{watchout\}", "\n[/Warning]\n", text)
    return text


def _clean_text_formatting(text: str) -> str:
    """Remove text formatting commands but keep the text."""
    replacements = {
        "\\textbf{": "",
        "\\emph{": "",
        "\\textit{": "",
        "\\textrm{": "",
        "\\textsf{": "",
        "\\texttt{": "",
        "\\mathrm{": "",
        "\\mathit{": "",
        "\\mathbf{": "",
        "\\mathsf{": "",
        "\\mathtt{": "",
        "}{": "",
        "}}": "",
        "}": "",
    }
    for latex, spoken in replacements.items():
        text = text.replace(latex, spoken)
    return text


def _clean_special_chars(text: str) -> str:
    """Clean up special LaTeX characters."""
    replacements = {
        "``": '"',
        "''": '"',
        "`": "'",
        "'": "'",
        "--": " – ",
        "---": " — ",
        "\\&": " and ",
        "\\$": "$",
        "\\%": "%",
        "\\_": "_",
        "\\#": "#",
        "\\{": "",
        "\\}": "",
        "~": " ",
        "\\quad": " ",
        "\\qquad": "  ",
        "\\,": " ",
        "\\;": " ",
        "\\!": "",
        "\\n": "\n",
        "\\\\": "\n",
        "\\newline": "\n",
        "\\ldots": "...",
        "\\dots": "...",
    }
    for latex, spoken in replacements.items():
        text = text.replace(latex, spoken)
    return text


def _final_cleanup(text: str) -> str:
    """Final cleanup pass."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n\n-", "\n-", text)
    text = re.sub(r"-\s+-", "-", text)
    text = re.sub(
        r"\[(Important Formula|Explanation|Warning|Theorem|Lemma|Corollary|Proposition|Definition|Axiom)\]\s*",
        r"\n\1: ",
        text,
    )
    text = re.sub(
        r"\[/(Important Formula|Explanation|Warning|Theorem|Lemma|Corollary|Proposition|Definition|Axiom)\]",
        "",
        text,
    )
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


class SmartLatexProcessor:
    """Smart LaTeX processor for TTS."""

    def __init__(self, latex_speak_mode: str = "math", verbosity: str = "short"):
        self.latex_processor = LatexProcessor(
            speak_mode=latex_speak_mode,
            verbosity=verbosity,
        )

    def process(self, latex_text: str) -> Tuple[str, bool]:
        """Process LaTeX document and return speech-ready text."""
        cleaned = clean_latex_document(latex_text)
        speech_text, processed = self.latex_processor.process(cleaned)
        speech_text = _final_cleanup(speech_text)
        return speech_text, processed


def smart_process_latex(
    latex_text: str,
    mode: str = "study",
    latex_speak_mode: str = "math",
    latex_verbosity: str = "short",
) -> str:
    """
    Smart process LaTeX document for TTS.
    """
    processor = SmartLatexProcessor(
        latex_speak_mode=latex_speak_mode, verbosity=latex_verbosity
    )

    text, _ = processor.process(latex_text)

    if mode == "study" and text:
        text = "Let's study this material together.\n\n" + text

    return text


if __name__ == "__main__":
    test_latex = r"""\documentclass{article}
\begin{document}
\section{The First Law of Thermodynamics}
\subsection{Systems and State Functions}
\begin{itemize}
    \item \textbf{System:} The part of the universe under observation.
    \item \textbf{State Function:} A property (like $U$, $H$, $S$, $G$).
\end{itemize}
\begin{equation}
    \Delta U = Q + W
\end{equation}
\begin{masterformula}{The First Law}
    The change in internal energy ($\Delta U$) equals heat ($Q$) plus work ($W$).
\end{masterformula}
\end{document}"""

    result = smart_process_latex(
        test_latex, mode="study", latex_speak_mode="math", latex_verbosity="detailed"
    )
    print("=" * 60)
    print("INPUT:")
    print(test_latex)
    print("=" * 60)
    print("OUTPUT:")
    print(result)
    print("=" * 60)
