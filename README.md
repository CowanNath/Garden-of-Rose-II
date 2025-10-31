# 🎬 Garden of Rose II

自动扫描媒体文件夹，智能识别番号系列文件，解析NFO元数据，并生成美观的Obsidian兼容Markdown笔记。支持完整的媒体库管理和分类展示。

## ✨ 功能特性

### 🎯 核心功能
- 🔍 **智能文件识别**: 支持多种番号格式（IPX-607, FC2-PPV-1234567, T-28633等）
- 📄 **NFO文件解析**: 多层次解析策略，智能恢复损坏的NFO文件
- 🎨 **美观模板**: 生成结构化的Markdown笔记，支持DataviewJS动态展示
- 🖼️ **媒体嵌入**: 支持封面、剧照、预告片等媒体文件的嵌入
- 🏷️ **智能分类**: 自动生成演员、关键词、系列、年份、评分分类页面

### 🛠️ 高级特性
- 📊 **Dataview集成**: 生成支持Obsidian Dataview查询的动态页面
- 🎭 **演员管理**: 自动生成演员作品集页面
- 🔖 **关键词系统**: 智能提取和关联关键词标签
- 📈 **评分统一**: 自动格式化评分为统一的一位小数格式
- 🎬 **预告片过滤**: 智能过滤过小的预告片文件（<500KB）
- 📝 **日志控制**: 可配置是否生成日志文件，保持目录整洁
- 🖼️ **封面处理**: 无封面时优雅隐藏，不显示占位符

## 🚀 快速开始

### 环境要求
- Python 3.7+
- 必需的Python包（见requirements.txt）

请先按照 [配置方法](配置方法.md) 文件配置obsidian设置和MDx配置

### 安装依赖

```bash
pip install -r requirements.txt
```


### 运行脚本

windows：
双击 启动媒体收集器.bat 即可运行程序。

```bash
# 使用默认配置运行
python media_collector.py

# 指定配置文件运行
python media_collector.py --config my_config.yaml

# 命令行覆盖配置参数
python media_collector.py --source-dir "/path/to/media" --output-dir "/path/to/output"
```

### 配置文件
编辑 `config.yaml` 文件来配置：
- 📁 源目录和输出目录路径
- 🔍 番号匹配规则
- 🏷️ 关键词和标签设置
- 📊 Markdown生成选项
- 🎨 Obsidian集成设置
- 📝 日志配置


## 📁 项目结构

```
media-collector/
├── 📄 media_collector.py          # 主脚本文件
├── 📄 nfo_parser_fixed.py         # NFO文件解析器
├── 📄 config.yaml                 # 配置文件
├── 📄 requirements.txt            # Python依赖列表
├── 📄 CLAUDE.md                   # 项目指导文档
├── 📄 README.md                   # 项目说明文档
├── 📁 css/                        # 样式文件目录
│   ├── 📄 hover-scroll.css        # 悬停预览样式(Obsidian插件优化)
│   └── 📄 v-video-page.css        # 视频页面专用样式
├── 📁 jav_store/                  # 生成的数据目录
│   ├── 📄 Preview.md               # 总预览页面(展示所有影片)
│   ├── 📁 films/                  # 影片详情页面
│   ├── 📁 actor/                  # 演员作品集页面
│   ├── 📁 keywords/               # 关键词分类页面
│   ├── 📁 series/                 # 系列作品页面
│   ├── 📁 years/                  # 年份分类页面
│   ├── 📁 ranks/                  # 评分分类页面
│   └── 📁 source/                 # 原始媒体文件目录
└── 📄 media_collector.log         # 日志文件(运行时生成，可配置)
```

## 🎯 生成的页面类型

### 📽️ 影片页面 (films/)
- 🖼️ 封面图片和剧照展示
- 📝 详细信息（标题、演员、时长、评分等）
- 🎬 预告片播放器（自动过滤小文件）
- 🔗 相关文件链接和分类标签
- 📊 DataviewJS动态内容展示

### 🎭 分类页面
- **总预览页面**: `Preview.md` - 展示所有影片的概览
- **演员页面**: 按演员分组显示所有作品
- **关键词页面**: 按关键词标签分类作品
- **系列页面**: 按系列作品分组显示
- **年份页面**: 按发行年份分类作品
- **评分页面**: 按评分等级分类作品

### 🎨 样式特性
- 🃏 卡片式布局，美观大方
- 📱 响应式设计，适配不同屏幕
- 🔍 图片预览和懒加载
- 🎭 内部链接和双向引用支持
- 🎨 自定义CSS样式优化
  - `hover-scroll.css` - 优化Obsidian悬停预览体验
  - `v-video-page.css` - 视频页面专用布局和样式

## 📄 支持的文件类型

### 🎬 视频文件
- **格式**: `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.strm`
- **功能**: 自动识别主视频文件和预告片

### 🖼️ 图片文件
- **格式**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.gif`
- **用途**: 封面、剧照、背景图等

### 📄 元数据文件
- **格式**: `.nfo`
- **内容**: 影片详细信息、演员、评分、剧情简介等
- **解析**: 多层次解析策略，容错性强

### 🔍 番号格式支持
- **标准格式**: `IPX-607`, `EDRG-009`, `ABP-408`
- **FC2格式**: `FC2-PPV-1234567`
- **特殊格式**: `T-28633` (Tokyo Hot)
- **其他**: 支持自定义正则表达式规则

## ⚙️ 配置说明

### 📂 路径配置
```yaml
paths:
  source_directories:
    - "./jav_store/source"        # 媒体文件源目录
  output_directory: "jav_store/films"   # Markdown输出目录
```

### 🔍 文件匹配规则
```yaml
file_patterns:
  code_patterns:
    - "([A-Z]+-\\d+)"        # 标准格式: IPX-607
    - "([A-Z]{2,}\\d{3,})"   # 紧凑格式: ABP408
    - "(FC2-\\d{7})"         # FC2格式: FC2-1234567
    - "(T-[A-Z0-9]+)"        # Tokyo Hot格式
```

## 🔧 故障排除

### 常见问题
1. **关键词页面无结果** → 确认影片的NFO文件中包含关键词标签
2. **预告片不显示** → 检查预告片文件是否大于500KB
3. **评分格式不统一** → 重新运行脚本统一格式化
4. **年份页面无内容** → 确认影片的Year字段格式正确

### 调试模式
```bash
# 启用详细日志
python media_collector.py --log-level DEBUG

# 指定配置文件
python media_collector.py --config debug_config.yaml
```
