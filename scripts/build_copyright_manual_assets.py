"""Build deterministic diagrams and real CLI captures for the V1.0 manual."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS = (1800, 1080)
BACKGROUND = "#F6F8FA"
INK = "#17212B"
MUTED = "#5E6B76"
NAVY = "#173B57"
BLUE = "#2D6EA3"
TEAL = "#237A75"
GREEN = "#3B7A57"
AMBER = "#B26A24"
RED = "#A44949"
PURPLE = "#75588D"
LINE = "#B9C6D0"
WHITE = "#FFFFFF"
LIGHT_BLUE = "#E8F1F8"
LIGHT_GREEN = "#E8F3EC"
LIGHT_AMBER = "#F8EFE2"
LIGHT_PURPLE = "#F0EAF5"
LIGHT_RED = "#F8EAEA"

CJK_FONT = Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
MONO_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")


@dataclass(frozen=True)
class CaptureCommand:
    argv: tuple[str, ...]
    shown: str | None = None
    max_output_lines: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--ss-screen-bin", type=Path, required=True)
    parser.add_argument("--tutorial-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def font(size: int, *, mono: bool = False) -> ImageFont.FreeTypeFont:
    path = MONO_FONT if mono else CJK_FONT
    if not path.is_file():
        raise FileNotFoundError(f"required documentation font is missing: {path}")
    return ImageFont.truetype(str(path), size=size)


def wrapped(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    text_font: ImageFont.FreeTypeFont,
    *,
    fill: str = INK,
) -> None:
    left, top, right, bottom = box
    value = wrapped(text, max(8, int((right - left) / (text_font.size * 0.85))))
    bounds = draw.multiline_textbbox((0, 0), value, font=text_font, spacing=8, align="center")
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.multiline_text(
        ((left + right - width) / 2, (top + bottom - height) / 2),
        value,
        font=text_font,
        fill=fill,
        spacing=8,
        align="center",
    )


def box(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    label: str,
    *,
    fill: str,
    outline: str,
    text_fill: str = INK,
    size: int = 30,
) -> None:
    draw.rounded_rectangle(bounds, radius=14, fill=fill, outline=outline, width=3)
    centered_text(draw, bounds, label, font(size), fill=text_fill)


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str = BLUE,
    width: int = 5,
) -> None:
    draw.line((start, end), fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 >= x1 else -1
        tip = [(x2, y2), (x2 - direction * 20, y2 - 11), (x2 - direction * 20, y2 + 11)]
    else:
        direction = 1 if y2 >= y1 else -1
        tip = [(x2, y2), (x2 - 11, y2 - direction * 20), (x2 + 11, y2 - direction * 20)]
    draw.polygon(tip, fill=color)


def diagram_base(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, CANVAS[0], 110), fill=NAVY)
    draw.text((70, 27), title, font=font(42), fill=WHITE)
    draw.text((72, 79), subtitle, font=font(20), fill="#D9E7F1")
    draw.line((70, 140, 1730, 140), fill=LINE, width=2)
    return image, draw


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", dpi=(160, 160), optimize=True)


def build_architecture(path: Path) -> None:
    image, draw = diagram_base(
        "SS-Screen V1.0 软件总体结构图", "用户接口、科学内核、外部计算与制品层"
    )
    layers = [
        (175, "用户接口层", ["CLI 主命令界面", "分阶段命令", "帮助与状态输出"], LIGHT_BLUE, BLUE),
        (
            360,
            "应用编排层",
            ["参数校验", "阶段调度", "失败/恢复", "审计汇总"],
            LIGHT_PURPLE,
            PURPLE,
        ),
        (
            545,
            "科学功能层",
            ["data 数据规范化", "pair 结构匹配与配对", "stability 稳定性", "recommend 推荐"],
            LIGHT_GREEN,
            GREEN,
        ),
        (
            730,
            "数据与外部边界",
            ["MP / WBM", "CSV/JSON/JSONL", "VASP/ABACUS/AiiDA", "模型与结构制品"],
            LIGHT_AMBER,
            AMBER,
        ),
    ]
    for top, label, modules, fill, outline in layers:
        draw.text((80, top + 46), label, font=font(28), fill=NAVY)
        start = 350
        gap = 25
        width = int((1360 - gap * (len(modules) - 1)) / len(modules))
        for index, module in enumerate(modules):
            left = start + index * (width + gap)
            box(
                draw,
                (left, top, left + width, top + 120),
                module,
                fill=fill,
                outline=outline,
                size=25,
            )
        if top < 730:
            arrow(draw, (1030, top + 125), (1030, top + 175), color=MUTED)
    draw.text(
        (80, 975),
        "原则：科学算法不依赖外部调度器；所有阶段通过版本化文件契约衔接。",
        font=font(24),
        fill=MUTED,
    )
    save(image, path)


def build_overall_workflow(path: Path) -> None:
    image, draw = diagram_base(
        "SS-Screen V1.0 端到端功能流程图", "Stage 1–11 主数据流与外部高精度带隙边界"
    )
    labels = [
        "1 数据集构建",
        "2 组成筛选",
        "3 结构描述",
        "4 环境匹配",
        "5 带隙交接",
        "6 端元配对",
        "7 SQS",
        "8 MACE弛豫",
        "9 混合焓/声子",
        "10 竞争相凸包",
        "11 综合推荐",
    ]
    colors = [
        (LIGHT_BLUE, BLUE),
        (LIGHT_GREEN, GREEN),
        (LIGHT_AMBER, AMBER),
        (LIGHT_PURPLE, PURPLE),
    ]
    positions: list[tuple[int, int, int, int]] = []
    for index, label in enumerate(labels):
        row = index // 4
        column = index % 4
        if row % 2 == 1:
            column = 3 - column
        left = 90 + column * 420
        top = 190 + row * 250
        bounds = (left, top, left + 330, top + 120)
        fill, outline = colors[index % len(colors)]
        box(draw, bounds, label, fill=fill, outline=outline, size=26)
        positions.append(bounds)
    for first, second in zip(positions, positions[1:], strict=False):
        f_left, f_top, f_right, f_bottom = first
        s_left, s_top, s_right, s_bottom = second
        if abs(s_top - f_top) < 20:
            if s_left > f_left:
                arrow(
                    draw,
                    (f_right + 5, (f_top + f_bottom) // 2),
                    (s_left - 10, (s_top + s_bottom) // 2),
                )
            else:
                arrow(
                    draw,
                    (f_left - 5, (f_top + f_bottom) // 2),
                    (s_right + 10, (s_top + s_bottom) // 2),
                )
        else:
            arrow(
                draw, ((f_left + f_right) // 2, f_bottom + 5), ((s_left + s_right) // 2, s_top - 10)
            )
    draw.rounded_rectangle((1250, 925, 1700, 1025), radius=12, fill=LIGHT_RED, outline=RED, width=3)
    centered_text(
        draw, (1250, 925, 1700, 1025), "外部 gap 计算：导出 → 执行 → 校验回填", font(23), fill=RED
    )
    save(image, path)


def build_module_dependencies(path: Path) -> None:
    image, draw = diagram_base("模块依赖与职责图", "src/ssscreen 正式源码的单向依赖关系")
    modules = {
        "cli": ((700, 190, 1100, 310), "cli/app.py\n命令、参数、状态输出", LIGHT_BLUE, BLUE),
        "data": ((120, 460, 530, 610), "data/\nMP、WBM、condense、I/O", LIGHT_GREEN, GREEN),
        "pair": ((695, 460, 1105, 610), "pair/\n组成、envmatch、gap、配对", LIGHT_PURPLE, PURPLE),
        "stability": (
            (1270, 460, 1680, 610),
            "stability/\nSQS、MLP、声子、凸包、推荐",
            LIGHT_AMBER,
            AMBER,
        ),
        "config": ((695, 780, 1105, 900), "config.py\n具名阈值与运行设置", WHITE, NAVY),
    }
    for bounds, label, fill, outline in modules.values():
        box(draw, bounds, label, fill=fill, outline=outline, size=27)
    for target in ("data", "pair", "stability"):
        bounds = modules[target][0]
        arrow(draw, (900, 315), ((bounds[0] + bounds[2]) // 2, bounds[1] - 10), color=BLUE)
    arrow(draw, (535, 535), (685, 535), color=GREEN)
    arrow(draw, (1110, 535), (1260, 535), color=PURPLE)
    for target in ("data", "pair", "stability"):
        bounds = modules[target][0]
        arrow(draw, (900, 775), ((bounds[0] + bounds[2]) // 2, bounds[3] + 10), color=NAVY)
    draw.text(
        (130, 975),
        "外部 VASP / ABACUS / AiiDA 仅通过 gap task/result 文件契约连接，不进入核心依赖。",
        font=font(23),
        fill=MUTED,
    )
    save(image, path)


def build_interface_boundary(path: Path) -> None:
    image, draw = diagram_base("接口设计逻辑框图", "输入、命令接口、外部计算接口与输出制品")
    columns = [
        (
            80,
            "输入接口",
            ["MP SQLite/API", "WBM extxyz", "用户结构", "配置参数"],
            LIGHT_GREEN,
            GREEN,
        ),
        (
            580,
            "软件命令接口",
            ["dataset / group", "gap-export/validate", "pair / stability", "recommend"],
            LIGHT_BLUE,
            BLUE,
        ),
        (
            1080,
            "文件与外部接口",
            ["CSV/JSON/JSONL", "CIF/POSCAR", "外部 gap 平台", "模型 checkpoint"],
            LIGHT_PURPLE,
            PURPLE,
        ),
        (1480, "输出", ["候选对", "SQS/谱图", "稳定性证据", "推荐报告"], LIGHT_AMBER, AMBER),
    ]
    for left, title, items, fill, outline in columns:
        draw.text((left, 185), title, font=font(31), fill=NAVY)
        for index, item in enumerate(items):
            bounds = (left, 255 + index * 155, left + 300, 355 + index * 155)
            box(draw, bounds, item, fill=fill, outline=outline, size=24)
    for x1, x2 in ((385, 560), (885, 1060), (1385, 1460)):
        arrow(draw, (x1, 555), (x2, 555), color=BLUE)
    draw.text(
        (90, 950),
        "接口约束：结构 SHA、设置 SHA、method、status 和 schema_version 共同确定结果身份。",
        font=font(24),
        fill=MUTED,
    )
    save(image, path)


def build_runtime_state(path: Path) -> None:
    image, draw = diagram_base(
        "运行状态与恢复设计", "每个阶段显式记录成功、失败、跳过及外部等待状态"
    )
    states = [
        ((100, 410, 390, 540), "PENDING\n待处理", LIGHT_BLUE, BLUE),
        ((500, 410, 790, 540), "RUNNING\n执行中", LIGHT_PURPLE, PURPLE),
        ((900, 210, 1240, 340), "SUCCESS\n结果可用", LIGHT_GREEN, GREEN),
        ((900, 410, 1240, 540), "WAITING_EXTERNAL\n外部计算交接", LIGHT_AMBER, AMBER),
        ((900, 610, 1240, 740), "FAILED / REJECTED\n失败或校验拒绝", LIGHT_RED, RED),
        ((1370, 410, 1690, 540), "RESUME / RETRY\n续算或重试", WHITE, NAVY),
    ]
    for bounds, label, fill, outline in states:
        box(draw, bounds, label, fill=fill, outline=outline, size=27)
    arrow(draw, (395, 475), (490, 475))
    arrow(draw, (795, 455), (890, 300), color=GREEN)
    arrow(draw, (795, 475), (890, 475), color=AMBER)
    arrow(draw, (795, 495), (890, 675), color=RED)
    arrow(draw, (1245, 475), (1360, 475), color=NAVY)
    arrow(draw, (1530, 400), (650, 350), color=NAVY)
    draw.text(
        (105, 880),
        "恢复依据：输入哈希、模型与设置指纹、原子写入结果、manifest 和每任务状态。",
        font=font(26),
        fill=MUTED,
    )
    save(image, path)


def build_flow(path: Path, title: str, subtitle: str, steps: Sequence[str]) -> None:
    image, draw = diagram_base(title, subtitle)
    fills = [(LIGHT_BLUE, BLUE), (LIGHT_GREEN, GREEN), (LIGHT_AMBER, AMBER), (LIGHT_PURPLE, PURPLE)]
    count = len(steps)
    top = 230
    gap = 50
    width = int((CANVAS[0] - 160 - gap * (count - 1)) / count)
    bounds_list = []
    for index, step in enumerate(steps):
        left = 80 + index * (width + gap)
        bounds = (left, top, left + width, top + 260)
        fill, outline = fills[index % len(fills)]
        box(draw, bounds, f"{index + 1}\n{step}", fill=fill, outline=outline, size=25)
        bounds_list.append(bounds)
    for first, second in zip(bounds_list, bounds_list[1:], strict=False):
        arrow(
            draw,
            (first[2] + 5, (first[1] + first[3]) // 2),
            (second[0] - 10, (second[1] + second[3]) // 2),
        )
    draw.rounded_rectangle((150, 650, 1650, 865), radius=16, fill=WHITE, outline=LINE, width=3)
    centered_text(
        draw,
        (180, 675, 1620, 840),
        "每一步均保留输入、参数、输出、状态与错误信息；失败记录不会被当作成功结果继续传播。",
        font(28),
        fill=MUTED,
    )
    save(image, path)


def sanitize(text: str, project_root: Path, work_dir: Path) -> str:
    value = text.replace(str(project_root), "$PROJECT").replace(str(work_dir), "$RUN")
    value = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", value)
    return value.rstrip()


def run_commands(
    commands: Sequence[CaptureCommand],
    *,
    cwd: Path,
    project_root: Path,
    work_dir: Path,
) -> tuple[str, int]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")
    transcript: list[str] = []
    final_code = 0
    for command in commands:
        shown = command.shown or shlex.join(command.argv)
        transcript.append(f"$ {sanitize(shown, project_root, work_dir)}")
        result = subprocess.run(
            command.argv,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        output = result.stdout
        if result.stderr:
            output += result.stderr
        if command.max_output_lines is not None:
            output_lines = output.splitlines()
            if len(output_lines) > command.max_output_lines:
                hidden = len(output_lines) - command.max_output_lines
                output = "\n".join(output_lines[: command.max_output_lines])
                output += f"\n... [{hidden} additional help lines omitted]"
        if output.strip():
            transcript.append(sanitize(output, project_root, work_dir))
        transcript.append(f"[exit {result.returncode}]")
        final_code = result.returncode
        if result.returncode != 0:
            break
    return "\n".join(transcript), final_code


def terminal_image(path: Path, title: str, transcript: str) -> None:
    logical_lines: list[str] = []
    for raw in transcript.splitlines():
        logical_lines.extend(textwrap.wrap(raw, width=116, replace_whitespace=False) or [""])
    body_font = font(23, mono=True)
    line_height = 34
    height = max(760, 150 + line_height * (len(logical_lines) + 2))
    image = Image.new("RGB", (1800, height), "#10161D")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1800, 62), fill="#26323D")
    for index, color in enumerate(("#E96B5F", "#E5B84C", "#5AB77A")):
        draw.ellipse((26 + index * 36, 20, 46 + index * 36, 40), fill=color)
    draw.text((145, 14), f"Terminal — SS-Screen V1.0 — {title}", font=font(27), fill=WHITE)
    draw.rectangle((0, 62, 1800, 102), fill="#18222B")
    draw.text(
        (26, 70),
        "COMMAND LINE INTERFACE  |  project environment active",
        font=font(19, mono=True),
        fill="#8EC7E8",
    )
    y = 128
    for line in logical_lines:
        color = "#D7E0E8"
        if line.startswith("$"):
            color = "#76D39A"
        elif line.startswith("[exit"):
            color = "#E7C46A" if line != "[exit 0]" else "#79BFE8"
        draw.text((30, y), line, font=body_font, fill=color)
        y += line_height
    save(image, path)


def preview_command(path: Path, lines: int = 8) -> CaptureCommand:
    code = (
        "from pathlib import Path; "
        f"p=Path({str(path)!r}); "
        f"print('\\n'.join(p.read_text(encoding='utf-8').splitlines()[:{lines}]))"
    )
    return CaptureCommand(
        (os.fspath(Path(os.sys.executable)), "-c", code), shown=f"preview {path} --lines {lines}"
    )


def projected_json_command(
    path: Path,
    expression: str,
    *,
    shown: str,
) -> CaptureCommand:
    code = (
        "import json; from pathlib import Path; "
        f"d=json.loads(Path({str(path)!r}).read_text(encoding='utf-8')); "
        f"print(json.dumps({expression}, indent=2, sort_keys=True))"
    )
    return CaptureCommand(
        (os.fspath(Path(os.sys.executable)), "-c", code),
        shown=shown,
    )


def relaxation_summary_command(path: Path) -> CaptureCommand:
    code = (
        "import json; from pathlib import Path; "
        f"rows=[json.loads(x) for x in Path({str(path)!r}).read_text(encoding='utf-8').splitlines() if x.strip()]; "
        "print('records=', len(rows)); "
        "[print(r.get('structure_id'), r.get('structure_role'), r.get('status'), "
        "'converged=', r.get('converged'), 'energy_eV_atom=', round(r.get('energy_per_atom_eV'), 6), "
        "'max_force=', round(r.get('max_force_eV_per_angstrom'), 6), "
        "'model=', r.get('backend', {}).get('model_name')) for r in rows]"
    )
    return CaptureCommand(
        (os.fspath(Path(os.sys.executable)), "-c", code),
        shown=f"summarize-relaxation {path}",
    )


def recommendation_rows_command(path: Path) -> CaptureCommand:
    code = (
        "import csv; from pathlib import Path; "
        f"rows=list(csv.DictReader(Path({str(path)!r}).open(encoding='utf-8'))); "
        "print('recommendations=', len(rows)); "
        "[print('pair=', r['pair_index'], 'structure=', r['structure_id'], "
        "'class=', r['classification'], 'level=', r['evidence_level'], "
        "'mixing_meV_atom=', r['mixing_enthalpy_meV_per_atom'], "
        "'phonon=', r['dynamical_status'], 'hull=', r['hull_signal']) for r in rows]"
    )
    return CaptureCommand(
        (os.fspath(Path(os.sys.executable)), "-c", code),
        shown=f"summarize-recommendations {path}",
    )


def build_cli_captures(
    *,
    root: Path,
    executable: Path,
    tutorial: Path,
    work: Path,
    output: Path,
) -> None:
    work.mkdir(parents=True, exist_ok=True)
    command = os.fspath(executable)
    terminal_image(
        output / "cli_01_version_and_main.png",
        "启动与主命令界面",
        run_commands(
            [
                CaptureCommand((os.fspath(os.sys.executable), "--version")),
                CaptureCommand((command, "--version")),
                CaptureCommand((command, "--help")),
            ],
            cwd=root,
            project_root=root,
            work_dir=work,
        )[0],
    )
    for filename, title, argv in (
        ("cli_02_dataset_menu.png", "数据集二级菜单", (command, "dataset", "--help")),
        ("cli_03_stability_menu.png", "稳定性二级菜单", (command, "stability", "--help")),
    ):
        transcript, code = run_commands(
            [CaptureCommand(argv)], cwd=root, project_root=root, work_dir=work
        )
        if code:
            raise RuntimeError(transcript)
        terminal_image(output / filename, title, transcript)

    candidates = work / "composition_candidates.csv"
    composition_summary = work / "composition_summary.json"
    groups = work / "groups.json"
    group_summary = work / "structure_summary.json"
    gap_tasks = work / "gap_tasks.csv"
    gap_template = work / "gap_results_template.csv"
    method_metadata = work / "method_metadata.json"
    normalized_gaps = work / "gap_results.normalized.csv"
    rejected_gaps = work / "gap_results.rejected.csv"
    gap_report = work / "gap_validation.json"
    pairs = work / "final_pairs.csv"
    pair_summary = work / "pair_summary.json"
    sqs_manifest = work / "sqs_manifest.jsonl"
    recommendations = work / "recommendations.csv"
    recommendation_report = work / "recommendation_report.md"
    recommendation_summary = work / "recommendation_summary.json"
    condensed_index = work / "condensed_index.csv"
    condensed_validation = work / "condensed_validation.csv"
    mixing_enthalpy = work / "mixing_enthalpy.csv"
    mixing_summary = work / "mixing_summary.json"
    gap_demo_structures = work / "gap_demo_structures"
    gap_demo_tasks = work / "gap_demo_tasks.csv"
    gap_demo_template = work / "gap_demo_results_template.csv"
    gap_demo_metadata = work / "gap_demo_method_metadata.json"

    sessions: list[tuple[str, str, list[CaptureCommand]]] = [
        (
            "cli_04_composition_screen.png",
            "组成模板筛选",
            [
                CaptureCommand(
                    (
                        command,
                        "composition-screen",
                        "--df",
                        os.fspath(tutorial / "01_dataset" / "mp-demo.df"),
                        "--max-bandgap",
                        "3.0",
                        "--max-e-hull",
                        "0.01",
                        "--output",
                        os.fspath(candidates),
                        "--summary",
                        os.fspath(composition_summary),
                    )
                ),
                preview_command(composition_summary),
            ],
        ),
        (
            "cli_05_structure_match.png",
            "结构匹配与分组",
            [
                CaptureCommand(
                    (
                        command,
                        "structure-match",
                        "--candidates",
                        os.fspath(candidates),
                        "--condensed-dir",
                        os.fspath(tutorial / "03_condensed" / "structures"),
                        "--output",
                        os.fspath(groups),
                        "--summary",
                        os.fspath(group_summary),
                    )
                ),
                preview_command(group_summary),
            ],
        ),
        (
            "cli_19_gap_export_inputs.png",
            "带隙任务导出前输入检查",
            [
                projected_json_command(
                    groups,
                    "{'group_count': len(d), 'group_size': d[0]['group_size'], "
                    "'material_ids': d[0]['mp_ids'], 'compositions': d[0]['compositions'], "
                    "'band_gaps_eV': d[0]['band_gaps']}",
                    shown="inspect-gap-export-inputs 04_groups/group_df.json",
                ),
                CaptureCommand(
                    (
                        os.fspath(os.sys.executable),
                        "-c",
                        "from pathlib import Path; "
                        f"p=Path({str(tutorial / '01_dataset' / 'mp-demo.df')!r}); "
                        "print('dataset=', p.name, 'exists=', p.is_file(), "
                        "'bytes=', p.stat().st_size)",
                    ),
                    shown="inspect-dataset 01_dataset/mp-demo.df",
                ),
            ],
        ),
        (
            "cli_20_gap_export_vasp.png",
            "VASP高精度带隙任务导出",
            [
                CaptureCommand(
                    (
                        command,
                        "gap-export",
                        "--groups",
                        os.fspath(groups),
                        "--dataset",
                        os.fspath(tutorial / "01_dataset" / "mp-demo.df"),
                        "--method",
                        "vasp-hse06-pbe54-nosoc-v1",
                        "--structure-dir",
                        os.fspath(gap_demo_structures),
                        "--structure-format",
                        "json",
                        "--structure-format",
                        "cif",
                        "--structure-format",
                        "poscar",
                        "--results-template",
                        os.fspath(gap_demo_template),
                        "--method-metadata-template",
                        os.fspath(gap_demo_metadata),
                        "--max-natoms",
                        "30",
                        "--output",
                        os.fspath(gap_demo_tasks),
                    )
                ),
            ],
        ),
        (
            "cli_21_gap_export_outputs.png",
            "带隙任务与结构文件检查",
            [
                CaptureCommand(
                    (
                        os.fspath(os.sys.executable),
                        "-c",
                        "from pathlib import Path; "
                        f"p=Path({str(gap_demo_structures)!r}); "
                        "files=sorted(x.name for x in p.iterdir() if x.is_file()); "
                        "print('structure_files=', len(files)); "
                        "[print(x) for x in files]",
                    ),
                    shown="list-exported-structures 05_gap/structures",
                ),
                CaptureCommand(
                    (
                        os.fspath(os.sys.executable),
                        "-c",
                        "import csv; from pathlib import Path; "
                        f"rows=list(csv.DictReader(Path({str(gap_demo_tasks)!r}).open(encoding='utf-8'))); "
                        "print('gap_tasks=', len(rows)); "
                        "[print(r['task_id'], r['material_id'], r['formula'], "
                        "r['method'], 'natoms='+r['natoms'], "
                        "'sha256='+r['structure_sha256'][:16]+'...') for r in rows]",
                    ),
                    shown="summarize-gap-tasks 05_gap/gap_tasks.csv",
                ),
            ],
        ),
        (
            "cli_22_gap_export_templates.png",
            "带隙结果与方法模板检查",
            [
                CaptureCommand(
                    (
                        os.fspath(os.sys.executable),
                        "-c",
                        "import csv; from pathlib import Path; "
                        f"rows=list(csv.DictReader(Path({str(gap_demo_template)!r}).open(encoding='utf-8'))); "
                        "print('result_template_rows=', len(rows)); "
                        "print('fields=', ', '.join(rows[0])); "
                        "[print(r['task_id'], r['material_id'], r['formula'], "
                        "'status='+r['status'], 'band_gap='+r['band_gap']) for r in rows]",
                    ),
                    shown="inspect-results-template 05_gap/gap_results_template.csv",
                ),
                projected_json_command(
                    gap_demo_metadata,
                    "{'schema_version': d['schema_version'], 'method': d['method'], "
                    "'calculator': d['calculator'], 'functional': d['functional'], "
                    "'soc': d['soc'], 'pseudopotential_family': d['pseudopotential_family'], "
                    "'kpoint_policy': d['kpoint_policy'], 'settings': d['settings']}",
                    shown="inspect-method-template 05_gap/method_metadata.json",
                ),
            ],
        ),
        (
            "cli_06_gap_export.png",
            "高精度带隙任务导出",
            [
                CaptureCommand(
                    (
                        command,
                        "gap-export",
                        "--groups",
                        os.fspath(groups),
                        "--dataset",
                        os.fspath(tutorial / "01_dataset" / "mp-demo.df"),
                        "--method",
                        "tutorial-synthetic-gap-v1",
                        "--structure-dir",
                        os.fspath(work / "gap_structures"),
                        "--results-template",
                        os.fspath(gap_template),
                        "--method-metadata-template",
                        os.fspath(method_metadata),
                        "--output",
                        os.fspath(gap_tasks),
                    )
                ),
                preview_command(gap_tasks, 5),
            ],
        ),
        (
            "cli_07_gap_validate.png",
            "外部带隙结果校验",
            [
                CaptureCommand(
                    (
                        command,
                        "gap-validate",
                        "--gaps",
                        os.fspath(tutorial / "05_bands" / "gap_results.synthetic.csv"),
                        "--tasks",
                        os.fspath(gap_tasks),
                        "--method-metadata",
                        os.fspath(tutorial / "05_bands" / "method_metadata.json"),
                        "--output",
                        os.fspath(normalized_gaps),
                        "--rejected",
                        os.fspath(rejected_gaps),
                        "--report",
                        os.fspath(gap_report),
                    )
                ),
                preview_command(gap_report, 10),
            ],
        ),
        (
            "cli_08_pair.png",
            "端元材料配对",
            [
                CaptureCommand(
                    (
                        command,
                        "pair",
                        "--groups",
                        os.fspath(groups),
                        "--gap-results",
                        os.fspath(normalized_gaps),
                        "--method",
                        "tutorial-synthetic-gap-v1",
                        "--output",
                        os.fspath(pairs),
                        "--summary",
                        os.fspath(pair_summary),
                    )
                ),
                preview_command(pairs, 5),
            ],
        ),
        (
            "cli_09_sqs.png",
            "SQS 合金结构生成",
            [
                CaptureCommand(
                    (
                        command,
                        "stability",
                        "sqs-generate",
                        "--pairs",
                        os.fspath(pairs),
                        "--dataset",
                        os.fspath(tutorial / "01_dataset" / "mp-demo.df"),
                        "--backend",
                        "random",
                        "--supercell",
                        "2,2,2",
                        "--target-fraction",
                        "0.5",
                        "--seed",
                        "7",
                        "--output-dir",
                        os.fspath(work / "sqs"),
                        "--manifest",
                        os.fspath(sqs_manifest),
                    )
                ),
                preview_command(sqs_manifest, 3),
            ],
        ),
        (
            "cli_10_recommend.png",
            "综合推荐与报告生成",
            [
                CaptureCommand(
                    (
                        command,
                        "recommend",
                        "--pairs",
                        os.fspath(tutorial / "06_pairs" / "final_pairs.csv"),
                        "--gap-results",
                        os.fspath(tutorial / "05_bands" / "gap_results.normalized.csv"),
                        "--mixing-enthalpy",
                        os.fspath(tutorial / "09_thermodynamics" / "mixing_enthalpy.csv"),
                        "--phonons",
                        os.fspath(tutorial / "10_phonons" / "phonon_summary.csv"),
                        "--phase-stability",
                        os.fspath(tutorial / "11_phase_diagram_offline" / "phase_stability.csv"),
                        "--output",
                        os.fspath(recommendations),
                        "--report",
                        os.fspath(recommendation_report),
                        "--summary",
                        os.fspath(recommendation_summary),
                    )
                ),
                preview_command(recommendation_summary, 12),
            ],
        ),
        (
            "cli_11_environment_check.png",
            "环境激活与安装检查",
            [
                CaptureCommand((os.fspath(os.sys.executable), "--version")),
                CaptureCommand(
                    (
                        os.fspath(os.sys.executable),
                        "-c",
                        "import ssscreen; print(ssscreen.__version__)",
                    ),
                    shown='python -c "import ssscreen; print(ssscreen.__version__)"',
                ),
                CaptureCommand((os.fspath(os.sys.executable), "-m", "pip", "check")),
                CaptureCommand((command, "--version")),
            ],
        ),
        (
            "cli_12_dataset_mp_artifact.png",
            "MP 数据任务入口与已有产物",
            [
                CaptureCommand((command, "dataset", "mp", "--help")),
                projected_json_command(
                    tutorial / "01_dataset" / "mp-demo.df.provenance.json",
                    "{'backend': d['backend'], 'row_count': d['row_count'], "
                    "'schema_version': d['schema_version'], 'tutorial_subset': d['tutorial_subset'], "
                    "'query': d['query'], 'database_sha256': d['database']['sha256'], "
                    "'database_size_bytes': d['database']['size_bytes']}",
                    shown="audit-dataset-provenance mp-demo.df.provenance.json",
                ),
            ],
        ),
        (
            "cli_13_condense_archive.png",
            "结构描述归档索引与校验",
            [
                CaptureCommand(
                    (
                        command,
                        "condense-index",
                        "--condensed-dir",
                        os.fspath(tutorial / "03_condensed" / "structures"),
                        "--output",
                        os.fspath(condensed_index),
                    )
                ),
                CaptureCommand(
                    (
                        command,
                        "condense-validate",
                        "--condensed-dir",
                        os.fspath(tutorial / "03_condensed" / "structures"),
                        "--output",
                        os.fspath(condensed_validation),
                    )
                ),
                preview_command(condensed_validation, 5),
            ],
        ),
        (
            "cli_14_relax_existing_result.png",
            "MACE 驰豫任务入口与已有结果",
            [
                CaptureCommand(
                    (command, "stability", "relax", "--help"),
                    max_output_lines=25,
                ),
                relaxation_summary_command(tutorial / "08_relaxation" / "relaxation_results.jsonl"),
            ],
        ),
        (
            "cli_15_mixing_enthalpy.png",
            "混合焓计算与汇总",
            [
                CaptureCommand(
                    (
                        command,
                        "stability",
                        "mixing-enthalpy",
                        "--pairs",
                        os.fspath(tutorial / "06_pairs" / "final_pairs.csv"),
                        "--relax-results",
                        os.fspath(tutorial / "08_relaxation" / "relaxation_results.jsonl"),
                        "--output",
                        os.fspath(mixing_enthalpy),
                        "--summary",
                        os.fspath(mixing_summary),
                    )
                ),
                preview_command(mixing_summary, 12),
            ],
        ),
        (
            "cli_16_phonon_existing_result.png",
            "声子收集入口与已有结果",
            [
                CaptureCommand(
                    (command, "stability", "phonon-collect", "--help"),
                    max_output_lines=24,
                ),
                preview_command(tutorial / "10_phonons" / "phonon_summary.json", 14),
            ],
        ),
        (
            "cli_17_phase_existing_result.png",
            "凸包任务入口与已有结果",
            [
                CaptureCommand(
                    (command, "stability", "convex-hull", "--help"),
                    max_output_lines=24,
                ),
                preview_command(
                    tutorial / "11_phase_diagram_offline" / "phase_stability_summary.json",
                    14,
                ),
            ],
        ),
        (
            "cli_18_full_workflow_acceptance.png",
            "完整流程验收与最终报告",
            [
                projected_json_command(
                    tutorial / "12_recommendation" / "recommendation_summary.json",
                    "{'schema_version': d['schema_version'], 'input_pair_count': d['input_pair_count'], "
                    "'recommendation_count': d['recommendation_count'], "
                    "'classification_counts': d['classification_counts'], "
                    "'evidence_level_counts': d['evidence_level_counts'], "
                    "'require_defects': d['require_defects']}",
                    shown="audit-final-recommendation recommendation_summary.json",
                ),
                recommendation_rows_command(tutorial / "12_recommendation" / "recommendations.csv"),
            ],
        ),
    ]
    for filename, title, commands in sessions:
        transcript, code = run_commands(
            commands,
            cwd=root,
            project_root=root,
            work_dir=work,
        )
        if code:
            raise RuntimeError(f"capture command failed for {title}:\n{transcript}")
        terminal_image(output / filename, title, transcript)

    phonon_source = next(
        (tutorial / "10_phonons" / "results").glob("*/phonon_band_dos.png"),
        None,
    )
    if phonon_source is None:
        raise FileNotFoundError("tutorial phonon plot is missing")
    shutil.copy2(phonon_source, output / "result_phonon_band_dos.png")


def write_manifest(output: Path) -> None:
    images = []
    for path in sorted(output.glob("*.png")):
        with Image.open(path) as image:
            images.append(
                {
                    "file": path.name,
                    "width": image.width,
                    "height": image.height,
                    "bytes": path.stat().st_size,
                }
            )
    (output / "assets_manifest.json").write_text(
        json.dumps({"schema_version": 1, "images": images}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    executable = args.ss_screen_bin.resolve()
    tutorial = args.tutorial_dir.resolve()
    work = args.work_dir.resolve()
    output = args.output_dir.resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"ss-screen executable is missing: {executable}")
    if not tutorial.is_dir():
        raise FileNotFoundError(f"tutorial directory is missing: {tutorial}")
    output.mkdir(parents=True, exist_ok=True)

    build_architecture(output / "diagram_01_architecture.png")
    build_overall_workflow(output / "diagram_02_overall_workflow.png")
    build_module_dependencies(output / "diagram_03_module_dependencies.png")
    build_interface_boundary(output / "diagram_04_interface_boundary.png")
    build_runtime_state(output / "diagram_05_runtime_state.png")
    flow_specs = [
        (
            "flow_01_dataset.png",
            "数据集与组成筛选流程",
            "Stage 1–2",
            ["读取 MP/WBM", "规范化字段", "稳定性过滤", "组成模板分组", "候选表"],
        ),
        (
            "flow_02_structure.png",
            "结构描述与匹配流程",
            "Stage 3–4",
            ["读取结构", "robocrys 凝练", "提取局部环境", "X 位替换", "StructureGroup"],
        ),
        (
            "flow_03_gap.png",
            "高精度带隙交接流程",
            "外部计算边界",
            ["导出任务与结构", "外部平台计算", "返回结果", "身份与数值校验", "规范化 gap"],
        ),
        (
            "flow_04_pair_sqs.png",
            "端元配对与 SQS 流程",
            "Stage 5–6",
            ["回填 gap", "验证组内多样性", "枚举端元对", "确定替位元素", "生成目标组分 SQS"],
        ),
        (
            "flow_05_relax_mixing.png",
            "弛豫与混合焓流程",
            "Stage 7–8",
            ["构建任务", "MACE 弛豫", "质量控制", "统一端元能量", "计算混合焓"],
        ),
        (
            "flow_06_phonon.png",
            "声子谱流程",
            "Stage 9",
            ["选择超胞", "生成位移", "计算力", "构建力常数", "频带/DOS与判定"],
        ),
        (
            "flow_07_phase.png",
            "竞争相与凸包流程",
            "Stage 10",
            ["确定化学体系", "查询 MP 竞争相", "统一 MLP 弛豫", "构建相图", "计算 hull 距离"],
        ),
        (
            "flow_08_recommend.png",
            "综合推荐流程",
            "Stage 11",
            ["连接材料对", "汇总 gap", "汇总三类稳定性", "检查兼容性", "分级与生成报告"],
        ),
    ]
    for filename, title, subtitle, steps in flow_specs:
        build_flow(output / filename, title, subtitle, steps)

    build_cli_captures(
        root=root,
        executable=executable,
        tutorial=tutorial,
        work=work,
        output=output,
    )
    write_manifest(output)
    print(f"built {len(list(output.glob('*.png')))} manual images in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
