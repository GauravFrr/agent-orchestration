import os
import logging
from app.tools.registry import register_tool

logger = logging.getLogger(__name__)

# Base directory for tool file I/O sandbox
SANDBOX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sandbox_dir"))

def ensure_sandbox():
    if not os.path.exists(SANDBOX_DIR):
        os.makedirs(SANDBOX_DIR, exist_ok=True)
        logger.info(f"Created file I/O sandbox directory: {SANDBOX_DIR}")

def resolve_path(filepath: str) -> str:
    """
    Resolves filepath relative to SANDBOX_DIR, preventing directory traversal.
    """
    ensure_sandbox()
    # Remove leading slash or backslash to treat path as relative
    clean_filepath = filepath.lstrip("/\\")
    resolved = os.path.abspath(os.path.join(SANDBOX_DIR, clean_filepath))
    
    # Check if resolved path is inside SANDBOX_DIR
    if not resolved.startswith(SANDBOX_DIR):
        raise PermissionError(f"Security Access Violation: Path '{filepath}' escapes sandbox boundary.")
    return resolved

def file_read(filepath: str) -> dict:
    """
    Read content from a file inside the scoped sandbox directory.
    """
    logger.info(f"Tool file_read called on: {filepath}")
    try:
        resolved = resolve_path(filepath)
        if not os.path.exists(resolved):
            return {"success": False, "error": f"File '{filepath}' not found."}
        
        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "content": content}
    except Exception as e:
        logger.error(f"file_read error: {str(e)}")
        return {"success": False, "error": str(e)}

def file_write(filepath: str, content: str) -> dict:
    """
    Write content to a file inside the scoped sandbox directory.
    """
    logger.info(f"Tool file_write called on: {filepath}")
    try:
        resolved = resolve_path(filepath)
        # Create directories in path if they don't exist
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "message": f"Successfully wrote to '{filepath}'."}
    except Exception as e:
        logger.error(f"file_write error: {str(e)}")
        return {"success": False, "error": str(e)}

# Auto-register tools
register_tool(
    name="file_read",
    description="Read file contents from the scoped sandbox environment.",
    allowed_specialists=["research", "data_analysis", "code_exec"],
    func=file_read,
    input_schema={
        "type": "object",
        "properties": {
            "filepath": {"type": "string", "description": "Name or relative path of the file to read"}
        },
        "required": ["filepath"]
    }
)

register_tool(
    name="file_write",
    description="Write content to a file in the scoped sandbox environment.",
    allowed_specialists=["data_analysis", "code_exec"],
    func=file_write,
    input_schema={
        "type": "object",
        "properties": {
            "filepath": {"type": "string", "description": "Name or relative path of the file to write"},
            "content": {"type": "string", "description": "Text content to write to the file"}
        },
        "required": ["filepath", "content"]
    }
)
