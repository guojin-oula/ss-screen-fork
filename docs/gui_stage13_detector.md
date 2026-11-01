# Stage 13｜探测器材料应用性能评估（GUI演示与带隙预筛）

此阶段在桌面 GUI 工程树的“结果与报告”下，位于 Stage 12 之后。新增阶段不修改现有 CLI 科学计算命令，不运行器件级仿真。

## 用户操作

1. 先完成 Stage 12 并生成 `12_recommend/recommendations.csv`。
2. 左侧工程树单击“13 探测器性能评估”。
3. 选择目标波长预设（1.0 / 2.0 / 4.0 / 10.0 μm），也可输入自定义波长。
4. 点击“读取工程结果”和“重新评估”。表格显示端元、估计合金带隙、截止波长、目标波段是否在带隙范围内、推荐证据与可选的器件指标。
5. 点击“导出评估 CSV”保存到 `13_detector/detector_assessment.csv`（可自定义路径）。
6. 若 Stage 12 尚无输出，点击“加载内置演示数据”查看界面。此功能使用虚构的端元、输入带隙和虚构的器件指标（R、暗电流、NEP、上升时间、光敏面积），**不能用于科研判断或对外宣称真实性能**。

## 计算逻辑与边界

- 有合金带隙 `alloy_gap_eV` / `gap_alloy_eV` / `band_gap_eV` 时，直接使用输入数值（来源标签明确）。
- 否则如果 `gap_a_eV`、`gap_b_eV` 和 `actual_fraction_b`（或 `target_fraction_b`）有效，按 `Eg(x)=(1-x)*Eg(A)+x*Eg(B)` 线性估算。未考虑弯曲参数、应变、缺陷或温度，因此属于简化模型，而非实际合金带隙测量。
- 采用 `λc(μm)=1.239841984/Eg(eV)` 计算光子带间跃迁的名义截止波长；`目标波长<=λc` 仅表示从带隙角度可能覆盖该波长，并不保证量子效率或信噪比。
- 使用 Stage 12 原有 `classification`、`energy_above_hull_eV_per_atom`、`dynamical_status`、`hull_signal` 作为稳定性证据，只展示原值，不额外判定可制备性。
- **响应率、暗电流、噪声等效功率、响应时间及比探测率不可从材料带隙可靠推断**；无外部数据时显示“—”。
- 如果外部提供有效光敏面积 `area_cm2` 与 NEP `nep_W_sqrtHz`，可由 `D*=sqrt(A)/NEP`（Jones）得到派生比探测率，其余字段不做拟合和补全。

## 可选器件数据表

默认读取 `13_detector/device_measurements.csv`；不存在时正常工作，器件指标留空。

按 `recommendation_id`（优先）或 `pair_index` 匹配，CSV列名如下：

```csv
recommendation_id,responsivity_A_W,dark_current_A,nep_W_sqrtHz,rise_time_ms,area_cm2,detectivity_jones
<真实推荐ID>,0.8,1e-9,1e-12,0.4,0.01,
```

上面的数值仅展示CSV列格式，不是该材料的真实测量值；填入真实数据前请核验器件条件、波长、温度、偏压和测量出处。

## 文件清单

- `src/ssscreen/detector.py`：标准库实现的带隙/器件证据计算和CSV导出
- `src/ssscreen/gui/detector_page.py`：PySide6可视化页面、工程CSV读取和演示模式
- `src/ssscreen/gui/metadata.py`：Stage 13工程树定义
- `src/ssscreen/gui/app.py`：Stage 13页面注册和工程树导航
- `src/ssscreen/gui/icons.py`：Stage 13图标
- `src/ssscreen/gui/project_file.py`：将第13阶段产物纳入.ssproject单文件归档
- `tests/test_detector.py`：预筛、缺失值、外部器件证据和导出的单元测试

## 验证

在项目`.venv`（含PySide6和pytest）中执行：

```bash
python -m pytest tests/test_detector.py -q
python -m ssscreen.gui.app
```

如独立打开 app.py 的方式与本地安装习惯不同，可使用项目现有的 `ss-screen-gui` 启动命令。
