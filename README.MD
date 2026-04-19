**完整的 `README.md`（直接复制使用）**

```markdown
# textual-toolkit

一个轻量、优雅的 **Textual** TUI 封装库，使用**装饰器**几行代码就能快速构建专业级的图形化命令行工具界面。

无需手动写布局、控件、日志捕获等繁琐代码，专注业务逻辑即可。

## ✨ 特性

- **左侧三级分级菜单**：类别 → 工具 → 方法，清晰组织你的工具集
- **右侧自动参数表单**：
  - `str`、`int`、`float`、`number` → 普通文本输入框
  - `Path` → 文本输入框（支持路径）
  - `list` → Textarea（读取时自动按换行符或英文逗号 `,` 分割成列表）
  - `lenear` → ListBox（列表选择框）
- **方法装饰器** 可设置名称、用途描述、每个参数的 placeholder 提示``
- **运行 / 停止按钮**：一键执行选中方法，支持线程/异步运行，可随时停止
- **底部实时日志区**：自动捕获 `print()` 和 `logging` 输出并显示
- 完全基于装饰器，代码简洁，易于维护

## 安装

```bash
# 从私有仓库安装（推荐）
pip install git+https://你的私有仓库地址.git

# 本地开发安装
pip install -e .
```

## 使用示例

```python
from pathlib import Path
import logging
from decotextual import register_tool, tool_method, run_tui


# 1. 在类上添加装饰器，定义类别和工具名称
@register_tool(category="文件处理", tool_name="文件工具箱")
class FileTool:

    # 2. 在方法上添加装饰器，设置名称、用途、参数提示
    @tool_method(
        name="读取文件内容",
        description="读取指定路径的文件并返回前100行内容",
        placeholders={
            "file_path": "请输入文件完整路径，例如 /data/log.txt",
            "tags": "输入标签，每行一个或用逗号分隔"
        }
    )
    def read_file(self, file_path: Path, line_count: int = 100, tags: list[str] = None):
        """你的业务逻辑"""
        logging.info(f"开始读取文件: {file_path}")
        print(f"读取 {file_path} 前 {line_count} 行...")

        # ... 你的代码 ...
        return "读取完成！"

    @tool_method(
        name="批量重命名",
        description="对目录下的文件进行批量重命名",
        placeholders={"directory": "目标文件夹路径"}
    )
    def batch_rename(self, directory: Path, prefix: str):
        pass  # 你的实现


if __name__ == "__main__":
    run_tui()  # 启动 TUI 界面
```

## 装饰器说明

### `@register_tool(category: str, tool_name: str)`
- 放在**类**上
- `category`：左侧第一级分类名称
- `tool_name`：左侧第二级工具名称

### `@tool_method(name: str, description: str, placeholders: dict = None)`
- 放在**方法**上
- `name`：方法在左侧第三级显示的名称
- `description`：方法用途描述（会在界面显示）
- `placeholders`：可选，参数名 → 提示文字（placeholder）

## 参数类型自动映射

| 参数类型          | 生成的控件       | 备注                              |
|-------------------|------------------|-----------------------------------|
| `str`, `int`, `float`, `number` | Text 输入框     | 普通文本输入                      |
| `Path`            | Text 输入框     | 路径输入                          |
| `list`            | Textarea        | 换行或 `,` 分割自动转 list       |
| `lenear`          | ListBox         | 列表选择框                        |

## 日志与输出

- 所有 `print()` 和 `logging` 输出会**自动**重定向到底部日志面板
- 支持实时滚动、颜色高亮
- 运行方法时日志自动清空或追加（可配置）

## 快速开始

1. `pip install -e .`
2. 参考上面的示例写一个类 + 两个方法
3. 运行 `python your_tool.py` 即可看到完整 TUI

---

**仓库结构建议**（可选）

```
textual-toolkit/
├── src/
│   └── textual_toolkit/
│       ├── __init__.py
│       ├── decorators.py
│       ├── tui_app.py
│       ├── widgets/
│       └── utils/
├── examples/
├── pyproject.toml
├── README.md
└── LICENSE
```

