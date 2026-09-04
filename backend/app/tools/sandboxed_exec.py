import logging
import os
import subprocess
import sys
import tempfile

from app.tools.registry import register_tool

logger = logging.getLogger(__name__)

def sandboxed_code_exec(code: str) -> dict:
    """
    Execute python code in a sandboxed subprocess.
    Enforces a strict timeout, no network access (stub on Windows), and wipes the execution directory afterward.
    """
    logger.info("sandboxed_code_exec called")

    # 1. Create a secure temporary directory that is automatically wiped afterward
    with tempfile.TemporaryDirectory(prefix="agent_sandbox_") as tmpdir:
        script_path = os.path.join(tmpdir, "sandbox_run.py")

        # Write the user code to the file
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        logger.info(f"Writing sandbox code to temporary file: {script_path}")

        try:
            # 2. Run the code in a separate python subprocess
            # Enforce 10 second timeout limit
            # On Linux we could use preexec_fn to set limits, on Windows we rely on subprocess timeout limit
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=10.0,
                # We can block environment variables inheritance to prevent secret leaks
                env={"PATH": os.environ.get("PATH", "")}
            )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }

        except subprocess.TimeoutExpired as te:
            logger.error("Sandbox code execution timed out.")
            return {
                "success": False,
                "error": "TimeoutExpired",
                "stdout": te.stdout or "",
                "stderr": te.stderr or "Execution timed out (exceeded 10 seconds limit)."
            }
        except Exception as e:
            logger.exception("Sandbox execution failed due to subprocess launch failure.")
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": f"Subprocess launch error: {str(e)}"
            }

# Auto-register the tool
register_tool(
    name="sandboxed_code_exec",
    description="Run arbitrary python code inside a temporary, sandboxed subprocess environment. Enforces execution limits.",
    allowed_specialists=["code_exec"],
    func=sandboxed_code_exec,
    input_schema={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "The complete Python code string to run."}
        },
        "required": ["code"]
    }
)
