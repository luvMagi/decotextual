from pathlib import Path
import logging
from textual_toolkit import register_tool, tool_method, run_tui, Linear


@register_tool(category="文件处理", tool_name="文件工具箱")
class FileTool:
    @tool_method(
        name="读取文件内容",
        description="读取指定路径的文件并返回前100行内容",
        placeholders={
            "file_path": "请输入文件完整路径，例如 /data/log.txt",
            "tags": "输入标签，每行一个或用逗号分隔"
        }
    )
    def read_file(self, file_path: Path, line_count: int = 100, tags: list = None):
        logging.info(f"开始读取文件: {file_path}")
        print(f"读取 {file_path} 前 {line_count} 行...")
        if tags:
            print(f"标签: {tags}")
        return "读取完成！"

    @tool_method(
        name="批量重命名",
        description="对目录下的文件进行批量重命名",
        placeholders={"directory": "目标文件夹路径"}
    )
    def batch_rename(self, directory: Path, prefix: str = "file_", mode: Linear = Linear("顺序编号", "时间戳", "MD5")):
        print(f"扫描目录: {directory}")
        print(f"前缀: {prefix}, 模式: {mode}")
        return "重命名完成！"


@register_tool(category="网络工具", tool_name="HTTP 工具")
class HttpTool:
    @tool_method(
        name="发送 GET 请求",
        description="向指定 URL 发送 HTTP GET 请求",
        placeholders={"url": "请输入 URL，例如 https://httpbin.org/get"}
    )
    def get_request(self, url: str, timeout: int = 10, headers: list = None):
        print(f"GET {url} (timeout={timeout}s)")
        if headers:
            print(f"Headers: {headers}")
        return "请求完成"


if __name__ == "__main__":
    run_tui()
