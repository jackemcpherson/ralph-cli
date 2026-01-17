"""Claude Code CLI wrapper service.

This module provides a service for invoking the Claude Code CLI
with support for interactive and print modes.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import TextIO

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ClaudeError(Exception):
    """Exception raised for Claude Code operation failures.

    Raised when Claude Code is not installed or a command fails.
    """


class ClaudeService(BaseModel):
    """Service for invoking Claude Code CLI.

    Provides methods for running Claude Code in interactive and print modes,
    with support for streaming output and verbose JSON display.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    working_dir: Path | None = None
    verbose: bool = False
    claude_command: str = "claude"
    stdout: TextIO = Field(default_factory=lambda: sys.stdout)
    stderr: TextIO = Field(default_factory=lambda: sys.stderr)

    def _stream_output(
        self,
        process: subprocess.Popen[str],
    ) -> tuple[str, str]:
        """Stream process output to terminal in real-time.

        Args:
            process: Running subprocess to stream from.

        Returns:
            Tuple of (stdout_content, stderr_content).
        """
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        if process.stdout:
            for line in process.stdout:
                stdout_lines.append(line)
                self.stdout.write(line)
                self.stdout.flush()

        if process.stderr:
            stderr_content = process.stderr.read()
            if stderr_content:
                stderr_lines.append(stderr_content)
                self.stderr.write(stderr_content)
                self.stderr.flush()

        return "".join(stdout_lines), "".join(stderr_lines)

    def _build_base_args(self) -> list[str]:
        """Build base command arguments for Claude CLI.

        Returns:
            List of base arguments.
        """
        args = [self.claude_command]

        if self.verbose:
            args.append("--verbose")

        return args

    def _run_process(self, args: list[str], stream: bool) -> tuple[str, int]:
        """Run a Claude CLI process and capture output.

        Args:
            args: Command arguments to run.
            stream: Whether to stream output to terminal.

        Returns:
            Tuple of (output_text, exit_code).

        Raises:
            ClaudeError: If Claude Code is not installed or command fails.
        """
        try:
            process = subprocess.Popen(
                args,
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if stream:
                stdout_content, _ = self._stream_output(process)
            else:
                stdout_content, stderr_content = process.communicate()
                if stderr_content:
                    self.stderr.write(stderr_content)
                    self.stderr.flush()

            return_code = process.wait()
            return stdout_content, return_code

        except FileNotFoundError as e:
            msg = "Claude Code CLI not found. "
            msg += f"Ensure '{self.claude_command}' is installed and in PATH."
            raise ClaudeError(msg) from e
        except subprocess.SubprocessError as e:
            raise ClaudeError(f"Failed to run Claude Code: {e}") from e

    def run_interactive(self, prompt: str | None = None) -> int:
        """Run Claude Code in interactive mode.

        Launches Claude Code interactively, allowing user input.
        If a prompt is provided, it will be passed as the initial prompt.

        Args:
            prompt: Optional initial prompt to start the conversation.

        Returns:
            Exit code from the Claude process.

        Raises:
            ClaudeError: If Claude Code is not installed or fails to start.
        """
        args = self._build_base_args()

        if prompt:
            args.append(prompt)

        try:
            result = subprocess.run(
                args,
                cwd=self.working_dir,
                text=True,
            )
            return result.returncode
        except FileNotFoundError as e:
            msg = "Claude Code CLI not found. "
            msg += f"Ensure '{self.claude_command}' is installed and in PATH."
            raise ClaudeError(msg) from e
        except subprocess.SubprocessError as e:
            raise ClaudeError(f"Failed to run Claude Code: {e}") from e

    def run_print_mode(
        self,
        prompt: str,
        *,
        stream: bool = True,
        model: str | None = None,
        max_turns: int | None = None,
        system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> tuple[str, int]:
        """Run Claude Code in print mode (-p flag).

        Executes a single prompt and returns the output.
        Supports streaming output to terminal in real-time.

        Args:
            prompt: The prompt to send to Claude.
            stream: Whether to stream output to terminal (default: True).
            model: Optional model to use (e.g., 'sonnet', 'opus').
            max_turns: Optional maximum number of agentic turns.
            system_prompt: Optional system prompt to use.
            allowed_tools: Optional list of allowed tools.

        Returns:
            Tuple of (output_text, exit_code).

        Raises:
            ClaudeError: If Claude Code is not installed or command fails.
        """
        args = self._build_base_args()
        args.extend(["--print", prompt])

        if model:
            args.extend(["--model", model])

        if max_turns is not None:
            args.extend(["--max-turns", str(max_turns)])

        if system_prompt:
            args.extend(["--system-prompt", system_prompt])

        if allowed_tools:
            for tool in allowed_tools:
                args.extend(["--allowedTools", tool])

        return self._run_process(args, stream)

    def run_with_output_format(
        self,
        prompt: str,
        output_format: str = "text",
        *,
        stream: bool = True,
        model: str | None = None,
        max_turns: int | None = None,
    ) -> tuple[str, int]:
        """Run Claude Code with a specific output format.

        Args:
            prompt: The prompt to send to Claude.
            output_format: Output format ('text', 'json', 'stream-json').
            stream: Whether to stream output to terminal.
            model: Optional model to use.
            max_turns: Optional maximum number of agentic turns.

        Returns:
            Tuple of (output_text, exit_code).

        Raises:
            ClaudeError: If Claude Code is not installed or command fails.
        """
        args = self._build_base_args()
        args.extend(["--print", prompt])
        args.extend(["--output-format", output_format])

        if model:
            args.extend(["--model", model])

        if max_turns is not None:
            args.extend(["--max-turns", str(max_turns)])

        return self._run_process(args, stream)
