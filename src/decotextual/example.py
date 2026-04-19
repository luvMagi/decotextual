from pathlib import Path
import logging
from decotextual import register_tool, tool_method, run_tui, Linear


@register_tool(category="File Tools", tool_name="File Utilities")
class FileTool:
    @tool_method(
        name="Read File",
        description="Read a file and return the first N lines",
        placeholders={
            "file_path": "Full path, e.g. /data/log.txt",
            "tags": "One tag per line, or comma-separated"
        }
    )
    def read_file(self, file_path: Path, line_count: int = 100, tags: list = None):
        logging.info(f"Reading file: {file_path}")
        print(f"Reading {file_path} — first {line_count} lines...")
        if tags:
            print(f"Tags: {tags}")
        return "Done"

    @tool_method(
        name="Batch Rename",
        description="Batch rename files in a directory",
        placeholders={"directory": "Target directory path"}
    )
    def batch_rename(self, directory: Path, prefix: str = "file_", mode: Linear = Linear("Sequential", "Timestamp", "MD5")):
        print(f"Scanning: {directory}")
        print(f"Prefix: {prefix}, Mode: {mode}")
        return "Rename complete"


@register_tool(category="Network Tools", tool_name="HTTP Utilities")
class HttpTool:
    @tool_method(
        name="GET Request",
        description="Send an HTTP GET request to the specified URL",
        placeholders={"url": "e.g. https://httpbin.org/get"}
    )
    def get_request(self, url: str, timeout: int = 10, headers: list = None):
        print(f"GET {url} (timeout={timeout}s)")
        if headers:
            print(f"Headers: {headers}")
        return "Request complete"


if __name__ == "__main__":
    run_tui()
