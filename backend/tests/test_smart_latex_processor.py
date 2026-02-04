"""Tests for the smart LaTeX processor module."""

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


class TestSmartLatexProcessor:
    """Tests for smart LaTeX document processing."""

    def test_basic_document_structure(self):
        """Test processing of basic LaTeX document with sections."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\documentclass{article}
\begin{document}
\section{Main Section}
\subsection{Subsection}
\section*{Unnumbered Section}
\end{document}"""

        result = smart_process_latex(
            latex, mode="default", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "=== Main Section ===" in result
        assert "== Subsection ==" in result
        assert "Unnumbered Section" in result

    def test_itemize_processing(self):
        """Test processing of itemize environments."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\begin{itemize}
    \item First item
    \item Second item
\end{itemize}"""

        result = smart_process_latex(
            latex, mode="default", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "- First item" in result
        assert "- Second item" in result

    def test_masterformula_processing(self):
        """Test processing of masterformula tcolorbox."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\begin{masterformula}{Energy Conservation}
E = mc^2
\end{masterformula}"""

        result = smart_process_latex(
            latex, mode="default", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "[Important Formula: Energy Conservation]" in result
        assert "E = mc" in result

    def test_explanation_processing(self):
        """Test processing of explanation tcolorbox."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\begin{explanation}
This is an explanation of the concept.
\end{explanation}"""

        result = smart_process_latex(
            latex, mode="default", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "Explanation:" in result
        assert "concept" in result

    def test_watchout_processing(self):
        """Test processing of watchout tcolorbox."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\begin{watchout}
Be careful with signs!
\end{watchout}"""

        result = smart_process_latex(
            latex, mode="default", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "[Warning / Important]" in result
        assert "signs" in result

    def test_math_expressions(self):
        """Test processing of inline math expressions."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""The equation is \$E = mc^2\$."""

        result = smart_process_latex(
            latex, mode="default", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "E = mc to the power of 2" in result

    def test_study_mode_prefix(self):
        """Test that study mode adds the prefix."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\section{Test}
Content here."""

        result = smart_process_latex(
            latex, mode="study", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "Let's study this material together." in result

    def test_thermodynamics_document(self):
        """Test processing of a thermodynamics-style document."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\documentclass{article}
\begin{document}
\section{The First Law of Thermodynamics}
\subsection{Systems and State Functions}
\begin{itemize}
    \item \textbf{System:} The part of the universe under observation.
    \item \textbf{State Function:} A property (like \$U\$, \$H\$, \$S\$, \$G\$).
\end{itemize}
\begin{masterformula}{The First Law}
The change in internal energy (\$\Delta U\$) equals heat (\$Q\$) plus work (\$W\$).
\end{masterformula}
\end{document}"""

        result = smart_process_latex(
            latex, mode="study", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "=== The First Law of Thermodynamics ===" in result
        assert "== Systems and State Functions ==" in result
        assert "System:" in result
        assert "[Important Formula: The First Law]" in result
        assert "Delta U" in result

    def test_complex_thermodynamics(self):
        """Test processing of complex thermodynamics document."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\documentclass{article}
\begin{document}
\section{Thermodynamics Fundamentals}
\subsection{First Law}
The first law states: \$\Delta U = Q - W\$.

\begin{itemize}
    \item System: The part under study
    \item Surroundings: Everything else
\end{itemize}

\subsection{Second Law}
Entropy: \$\Delta S \geq 0\$.

\begin{explanation}
Entropy measures disorder.
\end{explanation}

\begin{watchout}
Watch sign conventions!
\end{watchout}
\end{document}"""

        result = smart_process_latex(
            latex, mode="study", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "=== Thermodynamics Fundamentals ===" in result
        assert "== First Law ==" in result
        assert "Delta U = Q - W" in result
        assert "- System:" in result
        assert "Explanation:" in result
        assert "[Warning / Important]" in result

    def test_latex_commands_removal(self):
        """Test that LaTeX commands are properly removed."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\documentclass{article}
\usepackage{geometry}
\title{Test Title}
\begin{document}
\section{Test}
Content here.
\end{document}"""

        result = smart_process_latex(
            latex, mode="default", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "documentclass" not in result.lower()
        assert "usepackage" not in result.lower()
        assert "Test Title" not in result or "Test" in result

    def test_equation_environment(self):
        """Test processing of equation environments."""
        from backend.smart_latex_processor import smart_process_latex

        latex = r"""\documentclass{article}
\begin{document}
\begin{equation}
F = ma
\end{equation}
\end{document}"""

        result = smart_process_latex(
            latex, mode="default", latex_speak_mode="math", latex_verbosity="short"
        )

        assert "F = ma" in result
