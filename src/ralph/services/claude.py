"""Claude Code CLI wrapper service.

This module provides a service for invoking the Claude Code CLI
with support for interactive and print modes.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import TextIO

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Sentinel value to indicate a message boundary (end of an assistant turn)
MESSAGE_BOUNDARY = "\n"


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

    def _parse_stream_event(self, line: str) -> str | None:
        """Parse a stream-json line and return displayable text.

        Args:
            line: A single line from stream-json output.

        Returns:
            Extracted text for display, MESSAGE_BOUNDARY for message end,
            or None if no displayable text.
        """
        try:
            event = json.loads(line)
            event_type = event.get("type")

            # Detect message boundaries - end of content block or assistant turn
            # content_block_stop fires after each content block (text, tool_use)
            # message_stop fires at the end of the entire message
            # result fires at the end of the conversation
            if event_type in ("content_block_stop", "message_stop", "result"):
                return MESSAGE_BOUNDARY

            # Extract text from assistant message events
            # Each assistant event is a complete turn - add newline after text
            if event_type == "assistant":
                message = event.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        # Add newline after each assistant text turn for readability
                        return text + "\n" if text else None

            # Also handle content_block_delta events for streaming text
            if event_type == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    return delta.get("text", "")

        except json.JSONDecodeError:
            pass
        return None

    def _stream_output(
        self,
        process: subprocess.Popen[str],
        parse_json: bool = False,
    ) -> tuple[str, str]:
        """Stream process output to terminal in real-time.

        Args:
            process: Running subprocess to stream from.
            parse_json: If True, parse stream-json events and display text content.

        Returns:
            Tuple of (stdout_content, stderr_content).
            When parse_json is True, stdout_content is the extracted text.
        """
        collected_text: list[str] = []
        stderr_lines: list[str] = []

        if process.stdout:
            for line in process.stdout:
                if parse_json:
                    text = self._parse_stream_event(line.strip())
                    if text:
                        collected_text.append(text)
                        self.stdout.write(text)
                        self.stdout.flush()
                else:
                    collected_text.append(line)
                    self.stdout.write(line)
                    self.stdout.flush()

        if process.stderr:
            stderr_content = process.stderr.read()
            if stderr_content:
                stderr_lines.append(stderr_content)
                self.stderr.write(stderr_content)
                self.stderr.flush()

        return "".join(collected_text), "".join(stderr_lines)

    def _build_base_args(self) -> list[str]:
        """Build base command arguments for Claude CLI.

        Returns:
            List of base arguments.
        """
        args = [self.claude_command]

        if self.verbose:
            args.append("--verbose")

        return args

    def _run_process(
        self, args: list[str], stream: bool, parse_json: bool = False
    ) -> tuple[str, int]:
        """Run a Claude CLI process and capture output.

        Args:
            args: Command arguments to run.
            stream: Whether to stream output to terminal.
            parse_json: If True and streaming, parse stream-json events.

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
                stdout_content, _ = self._stream_output(process, parse_json=parse_json)
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

    def run_interactive(
        self,
        prompt: str | None = None,
        *,
        skip_permissions: bool = False,
    ) -> int:
        """Run Claude Code in interactive mode.

        Launches Claude Code interactively, allowing user input.
        If a prompt is provided, it will be passed as the initial prompt.

        Args:
            prompt: Optional initial prompt to start the conversation.
            skip_permissions: Whether to skip permission prompts (default: False).

        Returns:
            Exit code from the Claude process.

        Raises:
            ClaudeError: If Claude Code is not installed or fails to start.
        """
        args = self._build_base_args()

        if skip_permissions:
            args.append("--dangerously-skip-permissions")

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
        skip_permissions: bool = False,
        append_system_prompt: str | None = None,
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
            skip_permissions: Whether to skip permission prompts (default: False).
            append_system_prompt: Optional text to append to system prompt.

        Returns:
            Tuple of (output_text, exit_code).

        Raises:
            ClaudeError: If Claude Code is not installed or command fails.
        """
        args = self._build_base_args()
        args.extend(["--print", prompt])

        # stream-json output format requires --verbose flag.
        # We always add it when streaming, but only display raw JSON when
        # self.verbose=True (handled by parse_json logic in _stream_output).
        if stream and "--verbose" not in args:
            args.append("--verbose")

        if skip_permissions:
            args.append("--dangerously-skip-permissions")

        if model:
            args.extend(["--model", model])

        if max_turns is not None:
            args.extend(["--max-turns", str(max_turns)])

        if system_prompt:
            args.extend(["--system-prompt", system_prompt])

        if allowed_tools:
            for tool in allowed_tools:
                args.extend(["--allowedTools", tool])

        if append_system_prompt:
            args.extend(["--append-system-prompt", append_system_prompt])

        if stream:
            args.extend(["--output-format", "stream-json"])

        return self._run_process(args, stream, parse_json=stream)

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
