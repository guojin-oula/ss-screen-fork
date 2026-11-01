# SS-Screen V0.1.0 源程序鉴别材料

本目录保存“新材料计算筛选软件 V0.1.0”的源程序鉴别材料。

- `SS-Screen_V0.1.0_source_front2500_back2500.pdf`：A4 纵向 PDF，每页 50 行，共 100 页；前 50 页为正式包开头 2500 行，后 50 页为末尾 2500 行。
- `SS-Screen_V0.1.0_source_front2500_back2500_unlabeled.docx`：Word 版本，每页预设 50 行；正文仅保留原始源代码，删除选段编号、原文件行号、路径和分隔符等前置标号。
- `SS-Screen_V0.1.0_source_front2500_back2500.txt`：相同 5000 行的可检索文本，每行包含选段行号、源文件路径、原文件行号和完整源码。
- `SS-Screen_V0.1.0_source_front2500_back2500_manifest.json`：文件排序、源文件数量、总行数、选取边界和输出 SHA-256。

生成范围仅为 `src/ssscreen/**/*.py`。文件按 POSIX 路径升序排列，文件内保持原行序；测试、项目脚本、文档、历史参考和生成数据不计入源程序。运行以下命令可确定性重建：

```bash
source .venv/bin/activate
python scripts/build_copyright_source.py
```

正式提交前应再次确认申请表、操作手册和本材料的软件全称与版本号完全一致。
