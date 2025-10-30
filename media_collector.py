#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Media Collector to Obsidian Generator
扫描媒体文件夹，自动生成Obsidian格式的Markdown笔记
"""

# 在最开头强制禁用字节码缓存
import sys
sys.dont_write_bytecode = True

# 设置环境变量
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import os
import re
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import argparse
from datetime import datetime
import yaml
import logging
import html


@dataclass
class MediaInfo:
    """媒体文件信息数据类"""
    code: str  # 番号
    title: str = ""
    actors: List[str] = None
    release_date: str = ""
    rating: float = 0.0
    plot: str = ""
    genre: List[str] = None
    studio: str = ""
    director: str = ""
    series: str = ""  # 系列
    maker: str = ""  # 片商
    publisher: str = ""  # 发行商
    poster_path: str = ""
    fanart_path: str = ""
    video_path: str = ""
    trailer_path: str = ""
    nfo_path: str = ""

    def __post_init__(self):
        if self.actors is None:
            self.actors = []
        if self.genre is None:
            self.genre = []


class Config:
    """配置管理类"""

    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config = self.load_config()
        self.setup_logging()

    def load_config(self) -> dict:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                logging.info(f"配置文件加载成功: {self.config_file}")
                return config
            else:
                logging.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
                return self.get_default_config()
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return self.get_default_config()

    def get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            'basic': {
                'recursive': True,
                'encoding': 'utf-8',
                'datetime_format': "%Y-%m-%d %H:%M:%S"
            },
            'paths': {
                'source_directories': ['test_media'],
                'output_directory': 'obsidian_output'
            },
            'file_patterns': {
                'video_extensions': ['.mp4', '.mkv', '.avi', '.mov', '.wmv'],
                'strm_extensions': ['.strm'],
                'image_extensions': ['.jpg', '.jpeg', '.png', '.webp'],
                'poster_keywords': ['poster', 'cover', 'thumb'],
                'fanart_keywords': ['fanart', 'backdrop', 'background'],
                'trailer_keywords': ['trailer', 'preview', 'sample']
            },
            'nfo_parsing': {
                'defaults': {
                    'rating': 0.0,
                    'studio': '未知',
                    'director': '未知',
                    'plot': '暂无该部分信息'  # 硬编码的默认值，会被配置文件覆盖
                }
            },
            'advanced': {
                'log_level': 'INFO'
            }
        }

    def setup_logging(self):
        """设置日志"""
        log_level = self.config.get('advanced.log_level', 'INFO')
        enable_file_logging = self.config.get('advanced.logging.enable_file_logging', False)  # 默认禁用文件日志
        log_file_path = self.config.get('advanced.logging.log_file_path', 'media_collector.log')

        # 禁用所有logger的传播，只使用根logger
        logging.getLogger().handlers.clear()

        # 设置处理器列表
        handlers = [logging.StreamHandler()]

        # 如果启用文件日志，添加文件处理器
        if enable_file_logging:
            try:
                file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
                handlers.append(file_handler)
            except Exception as e:
                # 如果文件处理器创建失败，只使用控制台输出
                print(f"警告：无法创建日志文件 {log_file_path}: {e}")

        # 配置日志
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers,
            force=True  # 强制重新配置
        )

        # 禁用所有子logger的传播
        for name in logging.root.manager.loggerDict:
            logger = logging.getLogger(name)
            logger.propagate = False

    def get(self, key_path: str, default=None):
        """获取配置值，支持点分隔的路径"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


class ActorPageGenerator:
    """演员页面生成器"""

    def __init__(self, config: Config):
        self.config = config
        self.actor_dir = Path(config.get('paths.output_directory', 'obsidian_output')).parent / 'actor'
        self.actor_dir.mkdir(exist_ok=True)

    def generate_actor_pages(self, media_groups: Dict[str, MediaInfo]):
        """为所有演员生成页面"""
        # 收集所有演员和他们的作品
        actor_works = {}

        for code, media_info in media_groups.items():
            # 解析NFO文件获取演员信息
            actors = self._get_actors_from_media(media_info)
            for actor in actors:
                if actor not in ["未知演员", ""]:
                    if actor not in actor_works:
                        actor_works[actor] = []
                    actor_works[actor].append(media_info)

        # 为每个演员生成页面
        for actor, works in actor_works.items():
            self._generate_actor_page(actor, works)

        logging.info(f"已生成 {len(actor_works)} 个演员页面")

    def _get_actors_from_media(self, media_info: MediaInfo) -> List[str]:
        """从媒体信息中获取演员列表"""
        actors = []

        # 如果有NFO文件，解析获取演员
        if media_info.nfo_path and os.path.exists(media_info.nfo_path):
            try:
                nfo_parser = NFOParser(self.config)
                nfo_data = nfo_parser.parse_nfo(media_info.nfo_path)
                nfo_actors = nfo_data.get('actors', [])
                if nfo_actors:
                    actors.extend(nfo_actors)
            except Exception as e:
                logging.warning(f"解析NFO文件获取演员信息失败: {e}")

        # 如果NFO解析失败，使用media_info中的演员
        if not actors and media_info.actors:
            actors = media_info.actors

        return actors

    def _generate_actor_page(self, actor: str, works: List[MediaInfo]):
        """生成单个演员页面"""
        actor_file = self.actor_dir / f"{actor}.md"

        # 生成页面内容
        content = self._generate_actor_content(actor, works)

        # 写入文件
        with open(actor_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logging.info(f"已生成演员页面: {actor_file}")

    def _generate_actor_content(self, actor: str, works: List[MediaInfo]) -> str:
        """生成演员页面内容 - 基于preview.md的样式"""

        # 获取配置路径
        root_dir = self.config.get('dataview.root_dir', 'jav_store/source')
        actor_dir = f'{root_dir}/actor'
        years_dir = f'{root_dir}/years'
        ranks_dir = f'{root_dir}/ranks'
        keywords_dir = f'{root_dir}/keywords'

        # 按番号排序作品
        works_sorted = sorted(works, key=lambda x: x.code)

        content = f"""---
cssclasses:
  - cards-cols-6
  - cards-cover
  - table-max
  - cards
---

# 👰 演员: {actor}

```dataviewjs

// === 演员专属页面配置 ===
const ACTOR_NAME = "{actor}";
const ROOT = "jav_store";
const META_DIR = `${{ROOT}}/films`;
const COVER_DIR = `${{ROOT}}/source`;

// 分类目录常量
const ACTOR_DIR = `${{ROOT}}/actor`;
const YEARS_DIR = `${{ROOT}}/years`;
const RANKS_DIR = `${{ROOT}}/ranks`;
const SERIES_DIR = `${{ROOT}}/series`;
const KEYWORDS_DIR = `${{ROOT}}/keywords`;

// === 通用：把"文件名/相对路径/维基链接/Link对象"解析为 Obsidian 文件对象 ===
function resolveFile(anyPathLike, base){{
  if (!anyPathLike) return null;
  if (typeof anyPathLike === "string"){{
    const s = anyPathLike.trim();
    // [[...]] 维基链接
    const m = s.match(/^\\[\\[([^\\]#|]+)(?:#[^\\]|]+)?(?:\\|[^\\]]+)?\\]\\]$/);
    if (m) return app.metadataCache.getFirstLinkpathDest(m[1], base);
    // 普通相对路径
    return app.vault.getAbstractFileByPath(s);
  }}
  // Dataview 的链接对象
  if (anyPathLike?.path){{
    return app.vault.getAbstractFileByPath(anyPathLike.path)
        ?? app.metadataCache.getFirstLinkpathDest(anyPathLike.path, base);
  }}
  return null;
}}

// === 创建内部链接元素 ===
function makeILink(targetPathOrName, label, sourcePath){{
  const t = String(targetPathOrName ?? "").trim();
  const src = sourcePath ?? dv.current().file.path;
  const dest = app.metadataCache.getFirstLinkpathDest(t, src);
  const a = document.createElement('a');
  a.classList.add('internal-link');
  const href = dest ? dest.path : t;
  a.setAttribute('href', href);
  a.setAttribute('data-href', href);
  a.textContent = label ?? (dest ? dest.basename : t);
  return a;
}}

// === 封面查找：从source目录的番号文件夹中查找封面 ===
function findCoverForPage(p){{
  let v = p.Cover;
  if (!v) return null;

  // 直接按Cover路径解析
  let f = resolveFile(v, p.file.path);
  if (f) return f;

  // 兜底：在source目录的番号文件夹中查找封面
  const code = p.Code;
  if (code) {{
    // 生成可能的目录名称变体
    const getDirectoryVariants = (baseCode) => {{
      const variants = [baseCode];

      // 如果以数字结尾，尝试添加-C后缀
      if (/\\d+$/.test(baseCode)) {{
        variants.push(baseCode + '-C');
      }}

      // 如果已经以-C结尾，也尝试不带-C的版本
      if (baseCode.endsWith('-C')) {{
        variants.push(baseCode.slice(0, -2));
      }}

      return variants;
    }};

    const directoryVariants = getDirectoryVariants(code);

    // 尝试所有可能的目录名称变体
    for (const dirVariant of directoryVariants) {{
      const coverPaths = [
        `${{COVER_DIR}}/${{dirVariant}}/${{dirVariant}}-thumb.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/${{dirVariant}}-poster.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/poster.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/cover.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/thumb.jpg`
      ];

      for (const coverPath of coverPaths) {{
        const candidate = resolveFile(coverPath, p.file.path);
        if (candidate) return candidate;
      }}
    }}
  }}

  return null;
}}

// === 关键词页面所在文件夹 ===
const KW_DIR = KEYWORDS_DIR;

function kwLinksCell(p){{
  const raw = p.Keywords;
  let arr = [];

  // 统一成数组
  if (Array.isArray(raw)) {{
    arr = raw;
  }} else if (typeof raw === 'string') {{
    arr = raw.split(/[,，;；、\\s]+/);
  }} else {{
    arr = [];
  }}

  // 创建容器元素
  const container = document.createElement('div');
  container.className = 'kw-badges';

  // 逐个创建徽章元素
  arr.forEach(k => {{
    if (!k) return;

    let target, label;
    if (typeof k === 'object' && k.path) {{
      target = k.path;
      label = k.display ?? k.path.split('/').pop();
    }} else {{
      let t = String(k).trim();
      if (!t) return;
      if (/^\\[\\[.*\\]\\]$/.test(t)) {{
        // 已经是 [[...]] 格式
        const m = t.match(/^\\[\\[([^\\]#|]+)(?:#[^\\]|]+)?(?:\\|([^\\]]+))?\\]\\]$/);
        if (m) {{
          target = m[1];
          label = m[2] ?? m[1].split('/').pop();
        }}
      }} else {{
        // 普通字符串，添加目录前缀
        target = KW_DIR ? `${{KW_DIR}}/${{t}}` : t;
        label = t;
      }}
    }}

    // 创建徽章元素
    const badge = document.createElement('span');
    badge.className = 'kw';

    // 创建内部链接元素
    const link = makeILink(target, label, dv.current().file.path);
    badge.appendChild(link);

    container.appendChild(badge);
  }});

  return container;
}}

// === 获取当前演员的所有作品 ===
const actorPages = dv.pages(`"${{META_DIR}}"`).where(p => p.Actor === ACTOR_NAME).sort(p => p.Code ?? "", "asc");

// === 输出表格 ===
dv.table(
  ["Cover", "CN", "JP", "Code", "Year", "Time", "Rank", "Keywords"],
  actorPages.map(p => {{
    const coverFile = findCoverForPage(p);
    const coverHtml = coverFile
      ? `<img class="myTableImg" src="${{app.vault.adapter.getResourcePath(coverFile.path)}}" loading="lazy">`
      : `<div class="myTableImg no-cover-placeholder" style="
          width: 100px;
          height: 210px;
          border-radius: 8px;
          background: var(--background-secondary);
          border: 2px dashed var(--text-muted);
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
          box-sizing: border-box;
          margin: 0 auto;
        ">
          <div class="no-cover-text" style="
            color: var(--text-muted);
            font-size: 11px;
            font-weight: 500;
            text-align: center;
            line-height: 1.2;
            opacity: 0.8;
            user-select: none;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          ">No Cover</div>
        </div>`;

    return [
      coverHtml,
      "🇨🇳" + " " + (p.CN ?? ""),
      "🇯🇵" + " " + (p.JP ?? ""),
      "🪪 " + "[[" + (p.Code ?? "") + "]]",
      "📅 " + "[[" + (p.Year ? `${{YEARS_DIR}}/${{p.Year}}` : "") + "|" + (p.Year ?? "") + "]]",
      "🕒 " + (p.Time ?? ""),
      "🌡️ " + "[[" + (p.VideoRank ? `${{RANKS_DIR}}/${{p.VideoRank}}` : "") + "|" + (p.VideoRank ?? "") + "]]",
      kwLinksCell(p),
    ];
  }})
);

// === 统计信息 ===
const totalCount = actorPages.length;

// 计算年份分布
const yearCounts = {{}};
actorPages.forEach(p => {{
  const year = p.Year;
  if (year) {{
    yearCounts[year] = (yearCounts[year] || 0) + 1;
  }}
}});

const yearStats = Object.entries(yearCounts)
  .sort(([,a], [,b]) => a - b)
  .map(([year, count]) => `${{year}}年 (${{count}}部)`)
  .join(", ");

dv.paragraph(`**📊 作品总数**: ${{totalCount}} 部`);
dv.paragraph(`**📅 年份分布**: ${{yearStats}}`);
```
"""
        return content


class CategoryPageGenerator:
    """分类页面生成器 - 支持Keywords、Ranks、Series、Years"""

    def __init__(self, config: Config):
        self.config = config
        self.base_dir = Path(config.get('paths.output_directory', 'obsidian_output')).parent

    def generate_all_category_pages(self, media_groups: Dict[str, MediaInfo]):
        """生成所有分类页面"""
        categories = ['keywords', 'ranks', 'series', 'years']

        for category in categories:
            logging.info(f"开始生成{category}页面...")
            self._generate_category_pages(category, media_groups)

        logging.info("所有分类页面生成完成")

    def _generate_category_pages(self, category_type: str, media_groups: Dict[str, MediaInfo]):
        """生成特定类型的分类页面"""
        category_dir = self.base_dir / category_type
        category_dir.mkdir(exist_ok=True)

        # 收集分类和对应的作品
        category_works = {}

        for code, media_info in media_groups.items():
            # 解析NFO文件获取分类信息
            categories = self._get_category_from_media(media_info, category_type)
            for category in categories:
                if category not in ["", "未知", None]:
                    if category not in category_works:
                        category_works[category] = []
                    category_works[category].append(media_info)

        # 为每个分类生成页面
        for category, works in category_works.items():
            self._generate_category_page(category_type, category, works)

        logging.info(f"已生成 {len(category_works)} 个{category_type}页面")

    def _get_category_from_media(self, media_info: MediaInfo, category_type: str) -> List[str]:
        """从媒体信息中获取分类列表"""
        categories = []

        # 如果有NFO文件，解析获取分类信息
        if media_info.nfo_path and os.path.exists(media_info.nfo_path):
            try:
                nfo_parser = NFOParser(self.config)
                nfo_data = nfo_parser.parse_nfo(media_info.nfo_path)

                if category_type == 'keywords':
                    # 从genre字段获取关键词
                    genres = nfo_data.get('genre', [])
                    if genres:
                        categories.extend(genres)
                elif category_type == 'ranks':
                    # 从rating字段获取评分，统一格式化为一位小数
                    rating = nfo_data.get('rating', 0)
                    if rating > 0:
                        categories.append(str(round(rating, 1)))
                elif category_type == 'series':
                    # 从series字段获取系列
                    series = nfo_data.get('series', '')
                    if series and series.strip():
                        categories.append(series.strip())
                elif category_type == 'years':
                    # 从release_date字段获取年份
                    release_date = nfo_data.get('release_date', '')
                    if release_date:
                        year = self._extract_year_from_date(release_date)
                        if year and year != "未知":
                            categories.append(year)

            except Exception as e:
                logging.warning(f"解析NFO文件获取{category_type}信息失败: {e}")

        # 备用：从media_info直接获取
        if not categories:
            if category_type == 'keywords' and media_info.genre:
                categories.extend(media_info.genre)
            elif category_type == 'years' and media_info.release_date:
                year = self._extract_year_from_date(media_info.release_date)
                if year and year != "未知":
                    categories.append(year)

        return categories

    def _extract_year_from_date(self, date_str: str) -> str:
        """从日期字符串中提取年份"""
        import re
        year_match = re.search(r'(\d{4})', date_str)
        return year_match.group(1) if year_match else "未知"

    def _generate_category_page(self, category_type: str, category: str, works: List[MediaInfo]):
        """生成单个分类页面"""
        category_file = self.base_dir / category_type / f"{category}.md"

        # 生成页面内容
        content = self._generate_category_content(category_type, category, works)

        # 写入文件
        with open(category_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logging.info(f"已生成{category_type}页面: {category_file}")

    def _generate_category_content(self, category_type: str, category: str, works: List[MediaInfo]) -> str:
        """生成分类页面内容 - 基于preview.md的样式"""

        # 获取配置路径
        root_dir = self.config.get('dataview.root_dir', 'jav_store/source')

        # 根据分类类型设置配置
        type_configs = {
            'keywords': {
                'title': f"🏷️ {category}",
                'icon': '🏷️',
                'filter_field': 'Keywords',
                'dir': f'{root_dir}/keywords'
            },
            'ranks': {
                'title': f"⭐ {category}分",
                'icon': '⭐',
                'filter_field': 'VideoRank',
                'dir': f'{root_dir}/ranks'
            },
            'series': {
                'title': f"📺 {category}",
                'icon': '📺',
                'filter_field': 'Series',
                'dir': f'{root_dir}/series'
            },
            'years': {
                'title': f"📅 {category}年",
                'icon': '📅',
                'filter_field': 'Year',
                'dir': f'{root_dir}/years'
            }
        }

        config = type_configs.get(category_type, type_configs['keywords'])

        # 按番号排序作品
        works_sorted = sorted(works, key=lambda x: x.code)

        content = f"""---
cssclasses:
  - cards-cols-6
  - cards-cover
  - table-max
  - cards
---

# {config['title']}

```dataviewjs

// === 分类专属页面配置 ===
const CATEGORY_TYPE = "{category_type}";
const CATEGORY_VALUE = "{category}";
const ROOT = "jav_store";
const META_DIR = `${{ROOT}}/films`;
const COVER_DIR = `${{ROOT}}/source`;

// 分类目录常量
const ACTOR_DIR = `${{ROOT}}/actor`;
const YEARS_DIR = `${{ROOT}}/years`;
const RANKS_DIR = `${{ROOT}}/ranks`;
const SERIES_DIR = `${{ROOT}}/series`;
const KEYWORDS_DIR = `${{ROOT}}/keywords`;

// === 通用：把"文件名/相对路径/维基链接/Link对象"解析为 Obsidian 文件对象 ===
function resolveFile(anyPathLike, base){{
  if (!anyPathLike) return null;
  if (typeof anyPathLike === "string"){{
    const s = anyPathLike.trim();
    // [[...]] 维基链接
    const m = s.match(/^\\[\\[([^\\]#|]+)(?:#[^\\]|]+)?(?:\\|[^\\]]+)?\\]\\]$/);
    if (m) return app.metadataCache.getFirstLinkpathDest(m[1], base);
    // 普通相对路径
    return app.vault.getAbstractFileByPath(s);
  }}
  // Dataview 的链接对象
  if (anyPathLike?.path){{
    return app.vault.getAbstractFileByPath(anyPathLike.path)
        ?? app.metadataCache.getFirstLinkpathDest(anyPathLike.path, base);
  }}
  return null;
}}

// === 创建内部链接元素 ===
function makeILink(targetPathOrName, label, sourcePath){{
  const t = String(targetPathOrName ?? "").trim();
  const src = sourcePath ?? dv.current().file.path;
  const dest = app.metadataCache.getFirstLinkpathDest(t, src);
  const a = document.createElement('a');
  a.classList.add('internal-link');
  const href = dest ? dest.path : t;
  a.setAttribute('href', href);
  a.setAttribute('data-href', href);
  a.textContent = label ?? (dest ? dest.basename : t);
  return a;
}}

// === 封面查找：从source目录的番号文件夹中查找封面 ===
function findCoverForPage(p){{
  let v = p.Cover;
  if (!v) return null;

  // 直接按Cover路径解析
  let f = resolveFile(v, p.file.path);
  if (f) return f;

  // 兜底：在source目录的番号文件夹中查找封面
  const code = p.Code;
  if (code) {{
    // 生成可能的目录名称变体
    const getDirectoryVariants = (baseCode) => {{
      const variants = [baseCode];

      // 如果以数字结尾，尝试添加-C后缀
      if (/\\d+$/.test(baseCode)) {{
        variants.push(baseCode + '-C');
      }}

      // 如果已经以-C结尾，也尝试不带-C的版本
      if (baseCode.endsWith('-C')) {{
        variants.push(baseCode.slice(0, -2));
      }}

      return variants;
    }};

    const directoryVariants = getDirectoryVariants(code);

    // 尝试所有可能的目录名称变体
    for (const dirVariant of directoryVariants) {{
      const coverPaths = [
        `${{COVER_DIR}}/${{dirVariant}}/${{dirVariant}}-thumb.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/${{dirVariant}}-poster.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/poster.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/cover.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/thumb.jpg`
      ];

      for (const coverPath of coverPaths) {{
        const candidate = resolveFile(coverPath, p.file.path);
        if (candidate) return candidate;
      }}
    }}
  }}

  return null;
}}

// === 关键词页面所在文件夹 ===
const KW_DIR = KEYWORDS_DIR;

function kwLinksCell(p){{
  const raw = p.Keywords;
  let arr = [];

  // 统一成数组
  if (Array.isArray(raw)) {{
    arr = raw;
  }} else if (typeof raw === 'string') {{
    arr = raw.split(/[,，;；、\\s]+/);
  }} else {{
    arr = [];
  }}

  // 创建容器元素
  const container = document.createElement('div');
  container.className = 'kw-badges';

  // 逐个创建徽章元素
  arr.forEach(k => {{
    if (!k) return;

    let target, label;
    if (typeof k === 'object' && k.path) {{
      target = k.path;
      label = k.display ?? k.path.split('/').pop();
    }} else {{
      let t = String(k).trim();
      if (!t) return;
      if (/^\\[\\[.*\\]\\]$/.test(t)) {{
        // 已经是 [[...]] 格式
        const m = t.match(/^\\[\\[([^\\]#|]+)(?:#[^\\]|]+)?(?:\\|([^\\]]+))?\\]\\]$/);
        if (m) {{
          target = m[1];
          label = m[2] ?? m[1].split('/').pop();
        }}
      }} else {{
        // 普通字符串，添加目录前缀
        target = KW_DIR ? `${{KW_DIR}}/${{t}}` : t;
        label = t;
      }}
    }}

    // 创建徽章元素
    const badge = document.createElement('span');
    badge.className = 'kw';

    // 创建内部链接元素
    const link = makeILink(target, label, dv.current().file.path);
    badge.appendChild(link);

    container.appendChild(badge);
  }});

  return container;
}}

// === 根据分类类型获取过滤函数 ===
function filterByCategory(pages) {{
  if (CATEGORY_TYPE === 'keywords') {{
    // 关键词过滤：检查Keywords字段中是否包含当前关键词
    return pages.where(p => {{
      const keywords = p.Keywords || [];
      // 处理嵌套数组格式: [[- - keyword1], [- - keyword2]]
      const flattenKeywords = (arr) => {{
        let result = [];
        for (const item of arr) {{
          if (Array.isArray(item)) {{
            result = result.concat(flattenKeywords(item));
          }} else if (typeof item === 'string') {{
            result.push(item);
          }}
        }}
        return result;
      }};
      const keywordArray = flattenKeywords(keywords);
      return keywordArray.some(kw => {{
        if (typeof kw === 'object' && kw.path) {{
          return kw.path.split('/').pop() === CATEGORY_VALUE;
        }} else if (typeof kw === 'string') {{
          const cleanKw = kw.replace(/^\\[\\[|\\]\\]$/g, '').split('|').pop().trim();
          return cleanKw === CATEGORY_VALUE;
        }}
        return false;
      }});
    }});
  }} else {{
    // 其他分类：直接比较字段值
    if (CATEGORY_TYPE === 'ranks') {{
      return pages.where(p => p.VideoRank == CATEGORY_VALUE);
    }} else if (CATEGORY_TYPE === 'series') {{
      return pages.where(p => p.Series === CATEGORY_VALUE);
    }} else if (CATEGORY_TYPE === 'years') {{
      return pages.where(p => p.Year === CATEGORY_VALUE);
    }} else {{
      return pages.where(p => p[CATEGORY_TYPE.charAt(0).toUpperCase() + CATEGORY_TYPE.slice(1, -1)] === CATEGORY_VALUE);
    }}
  }}
}}

// === 获取当前分类的所有作品 ===
const allPages = dv.pages(`"${{META_DIR}}"`);
const categoryPages = filterByCategory(allPages).sort(p => p.Code ?? "", "asc");


// === 输出表格 ===
dv.table(
  ["Cover", "CN", "JP", "Code", "Actor", "Time", "Rank", "Keywords"],
  categoryPages.map(p => {{
    const coverFile = findCoverForPage(p);
    const coverHtml = coverFile
      ? `<img class="myTableImg" src="${{app.vault.adapter.getResourcePath(coverFile.path)}}" loading="lazy">`
      : `<div class="myTableImg no-cover-placeholder" style="
          width: 100px;
          height: 210px;
          border-radius: 8px;
          background: var(--background-secondary);
          border: 2px dashed var(--text-muted);
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
          box-sizing: border-box;
          margin: 0 auto;
        ">
          <div class="no-cover-text" style="
            color: var(--text-muted);
            font-size: 11px;
            font-weight: 500;
            text-align: center;
            line-height: 1.2;
            opacity: 0.8;
            user-select: none;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          ">No Cover</div>
        </div>`;

    return [
      coverHtml,
      "🇨🇳" + " " + (p.CN ?? ""),
      "🇯🇵" + " " + (p.JP ?? ""),
      "🪪 " + "[[" + (p.Code ?? "") + "]]",
      "👰 " + "[[" + (p.Actor ? `${{ACTOR_DIR}}/${{p.Actor}}` : "") + "|" + (p.Actor ?? "") + "]]",
      "🕒 " + (p.Time ?? ""),
      "🌡️ " + "[[" + (p.VideoRank ? `${{RANKS_DIR}}/${{p.VideoRank}}` : "") + "|" + (p.VideoRank ?? "") + "]]",
      kwLinksCell(p),
    ];
  }})
);

// === 统计信息 ===
const totalCount = categoryPages.length;

// 根据分类类型计算不同的统计信息
let statsText = `**📊 作品总数**: ${{totalCount}} 部`;

if (CATEGORY_TYPE === 'years') {{
  // 年份分类：计算月份分布
  const monthCounts = {{}};
  categoryPages.forEach(p => {{
    const date = p.file.path.split('/').pop().replace('.md', '');
    // 这里可以添加更复杂的月份统计逻辑
  }});
  statsText += `\\n**📅 年度作品**: ${{totalCount}} 部`;
}} else if (CATEGORY_TYPE === 'ranks') {{
  // 评分分类：计算平均评分等
  statsText += `\\n**⭐ 评分级别**: ${{CATEGORY_VALUE}}分`;
}} else if (CATEGORY_TYPE === 'series') {{
  // 系列分类：显示系列信息
  statsText += `\\n**📺 系列作品**: ${{CATEGORY_VALUE}}`;
}} else if (CATEGORY_TYPE === 'keywords') {{
  // 关键词分类：显示其他相关关键词
  statsText += `\\n**🏷️ 关键词**: ${{CATEGORY_VALUE}}`;
}}

dv.paragraph(statsText);
```
"""
        return content


class MediaScanner:
    """媒体文件扫描器"""

    def __init__(self, config: Config):
        self.config = config

        # 从配置获取路径
        source_dirs = config.get('paths.source_directories', ['test_media'])
        self.source_dirs = [Path(d) for d in source_dirs]

        self.output_dir = Path(config.get('paths.output_directory', 'obsidian_output'))
        self.output_dir.mkdir(exist_ok=True)

        # 从配置获取文件扩展名
        self.video_extensions = set(config.get('file_patterns.video_extensions',
                                             ['.mp4', '.mkv', '.avi', '.mov', '.wmv']))
        self.strm_extensions = set(config.get('file_patterns.strm_extensions', ['.strm']))
        self.image_extensions = set(config.get('file_patterns.image_extensions',
                                              ['.jpg', '.jpeg', '.png', '.webp']))

        # 获取文件关键词
        self.poster_keywords = config.get('file_patterns.poster_keywords',
                                          ['poster', 'cover', 'thumb'])
        self.fanart_keywords = config.get('file_patterns.fanart_keywords',
                                          ['fanart', 'backdrop', 'background'])
        self.trailer_keywords = config.get('file_patterns.trailer_keywords',
                                           ['trailer', 'preview', 'sample'])

    def scan_directory(self) -> Dict[str, MediaInfo]:
        """扫描目录，按番号分组文件"""
        media_groups = {}
        recursive = self.config.get('basic.recursive', True)

        # 获取所有文件
        all_files = []
        for source_dir in self.source_dirs:
            if source_dir.exists():
                logging.info(f"扫描目录: {source_dir}")
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        file_path = Path(root) / file
                        all_files.append(file_path)

                    # 如果不递归，清空子目录列表
                    if not recursive:
                        dirs.clear()

        # 按番号分组
        for file_path in all_files:
            code = self.extract_code_from_filename(file_path.name)
            if not code:
                continue

            if code not in media_groups:
                media_groups[code] = MediaInfo(code=code)

            # 分类文件
            self.categorize_file(file_path, media_groups[code])

        return media_groups

    def extract_code_from_filename(self, filename: str) -> Optional[str]:
        """从文件名中提取基础番号，忽略文件类型后缀"""
        # 从配置获取番号格式 - 修改为只提取基础番号
        patterns = self.config.get('file_patterns.code_patterns', [
            r'([A-Z]+-\d+)(?:-[A-Z])?',  # 标准格式: EDRG-009, EDRG-009-F
            r'([A-Z]{2,}\d{3,})',        # 无分隔符: ABC123
            r'(FC2-\d{7})',              # FC2格式
        ])

        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                # 只返回基础番号部分，忽略后缀
                base_code = match.group(1).upper()
                return base_code

        return None

    def extract_file_type(self, filename: str) -> Optional[str]:
        """从文件名中提取文件类型后缀"""
        # 检查文件类型后缀
        patterns = [
            r'[A-Z]+-\d+-([A-Z])\.',     # EDRG-009-F -> F
            r'[A-Z]+-\d+-([A-Z]+)\.',    # EDRG-009-TRAILER -> TRAILER
            r'[A-Z]+-\d+-thumb\.',       # 缩略图
            r'[A-Z]+-\d+-trailer\.',     # 预告片
        ]

        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        # 检查文件名关键词
        filename_lower = filename.lower()
        if 'poster' in filename_lower:
            return 'POSTER'
        elif 'fanart' in filename_lower:
            return 'FANART'
        elif 'trailer' in filename_lower:
            return 'TRAILER'
        elif 'thumb' in filename_lower:
            return 'THUMB'

        return None

    def categorize_file(self, file_path: Path, media_info: MediaInfo):
        """将文件分类到媒体信息中"""
        ext = file_path.suffix.lower()
        filename = file_path.name.lower()

        # 主视频文件处理
        if ext in self.video_extensions or ext in self.strm_extensions:
            # 检查是否是主视频文件（没有特殊后缀）
            file_type = self.extract_file_type(file_path.name)
            if not file_type or file_type in ['MAIN', 'VIDEO']:
                media_info.video_path = str(file_path)
            elif file_type == 'TRAILER':
                media_info.trailer_path = str(file_path)
        elif ext == '.nfo':
            media_info.nfo_path = str(file_path)
        elif ext in self.image_extensions:
            file_type = self.extract_file_type(file_path.name)
            if file_type == 'POSTER' or any(keyword in filename for keyword in self.poster_keywords):
                media_info.poster_path = str(file_path)
            elif file_type == 'FANART' or any(keyword in filename for keyword in self.fanart_keywords):
                media_info.fanart_path = str(file_path)
            elif file_type == 'THUMB':
                # 缩略图通常作为海报的补充
                if not media_info.poster_path:
                    media_info.poster_path = str(file_path)


class NFOParser:
    """NFO文件解析器"""

    def __init__(self, config: Config):
        self.config = config
        self.defaults = config.get('nfo_parsing.defaults', {
            'rating': 0.0,
            'studio': '未知',
            'director': '未知',
            'plot': '暂无该部分信息'  # 硬编码的默认值，会被配置文件覆盖
        })

    def parse_nfo(self, nfo_path: str) -> dict:
        """解析NFO文件，增加容错性"""
        logging.info(f"开始解析NFO文件: {nfo_path}")

        # 初始化数据结构，确保所有字段都存在
        data = {
            'title': '',
            'actors': [],
            'release_date': '',
            'rating': self.defaults.get('rating', 0.0),
            'plot': self.defaults.get('plot', '暂无该部分信息'),
            'genre': [],  # 确保genre列表初始化
            'studio': self.defaults.get('studio', '未知'),
            'director': self.defaults.get('director', '未知')
        }

        try:
            # 第一步：尝试标准解析
            logging.debug(f"尝试标准XML解析: {nfo_path}")
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            result = self._extract_xml_data(root, data)
            logging.info(f"标准解析成功: {nfo_path}")
            return result

        except (ParseError, ET.ParseError) as e:
            logging.warning(f"NFO文件XML格式错误: {nfo_path} - {e}")
            # 第二步：尝试修复XML文件并重新解析
            try:
                result = self._parse_nfo_with_recovery(nfo_path, data)
                logging.info(f"修复解析成功: {nfo_path}")
                return result
            except Exception as recovery_error:
                logging.error(f"修复解析也失败: {nfo_path} - {recovery_error}")
                return data

        except Exception as e:
            logging.error(f"解析NFO文件完全失败: {nfo_path} - {e}")
            # 打印详细的堆栈信息用于调试
            import traceback
            logging.debug(f"错误详情: {traceback.format_exc()}")
            return data

    def _extract_xml_data(self, root, data: dict) -> dict:
        """从XML根节点提取数据"""
        # 提取基本信息
        title_elem = root.find('title')
        if title_elem is not None and title_elem.text:
            data['title'] = self._clean_text(title_elem.text)

        # 提取原始标题
        originaltitle_elem = root.find('originaltitle')
        if originaltitle_elem is not None and originaltitle_elem.text:
            data['originaltitle'] = self._clean_text(originaltitle_elem.text)

        # 提取评分
        rating_elem = root.find('rating')
        if rating_elem is not None and rating_elem.text:
            try:
                rating = float(rating_elem.text)
                # 统一格式化为一位小数，如果是整数则显示为X.0
                data['rating'] = round(rating, 1)
            except ValueError:
                pass

        # 提取发行日期
        date_fields = ['releasedate', 'premiered', 'release']
        for field in date_fields:
            elem = root.find(field)
            if elem is not None and elem.text:
                data['release_date'] = self._clean_text(elem.text)
                break

        # 提取工作室
        studio_elem = root.find('studio')
        if studio_elem is not None and studio_elem.text:
            data['studio'] = self._clean_text(studio_elem.text)

        # 提取导演
        director_elem = root.find('director')
        if director_elem is not None and director_elem.text:
            data['director'] = self._clean_text(director_elem.text)

        # 提取剧情简介
        plot_elem = root.find('plot')
        if plot_elem is not None and plot_elem.text:
            data['plot'] = self._clean_text(plot_elem.text)

        # 提取类型
        for genre_elem in root.findall('genre'):
            if genre_elem.text:
                genre = self._clean_text(genre.text)
                if genre:
                    data['genre'].append(genre)

        # 提取演员
        for actor_elem in root.findall('actor'):
            name_elem = actor_elem.find('name')
            if name_elem is not None and name_elem.text:
                actor = self._clean_text(name_elem.text)
                if actor:
                    data['actors'].append(actor)

        return data

    def _clean_text(self, text: str) -> str:
        """清理文本，去除HTML实体和无效字符"""
        if not text:
            return ''

        # HTML实体解码
        text = html.unescape(text)

        # 移除无效字符
        # 保留可打印字符、中文、日文等
        import unicodedata
        cleaned = ''.join(char for char in text if unicodedata.category(char)[0] != 'C')

        return cleaned.strip()

    def _parse_nfo_with_recovery(self, nfo_path: str, data: dict) -> dict:
        """尝试修复损坏的NFO文件"""
        try:
            with open(nfo_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # 尝试修复常见的XML问题
            content = self._fix_xml_issues(content)

            # 创建临时文件解析
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.nfo', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                tree = ET.parse(temp_file_path)
                root = tree.getroot()
                # 创建新的数据字典，避免修改传入的data
                recovered_data = {
                    'title': '',
                    'actors': [],
                    'release_date': '',
                    'rating': self.defaults.get('rating', 0.0),
                    'plot': self.defaults.get('plot', '暂无该部分信息'),
                    'genre': [],
                    'studio': self.defaults.get('studio', '未知'),
                    'director': self.defaults.get('director', '未知')
                }
                recovered_data = self._extract_xml_data(root, recovered_data)
                logging.info(f"成功修复NFO文件: {nfo_path}")
                return recovered_data
            finally:
                os.unlink(temp_file_path)

        except Exception as e:
            logging.warning(f"无法修复NFO文件 {nfo_path}: {e}")

        return data

    def _fix_xml_issues(self, content: str) -> str:
        """修复常见的XML问题"""
        # 移除或替换无效字符
        import re

        # 替换常见的XML无效字符
        replacements = [
            (r'[\x00-\x08\x0B\x0C\x0E-\x1F]'),  # 控制字符
            (r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)'),  # 无效的实体引用
        ]

        for pattern in replacements:
            content = re.sub(pattern, '', content)

        # 确保XML标签闭合
        content = re.sub(r'&(?=amp|lt|gt|quot|apos)', '&amp;', content)

        return content


# 导入修复的NFO解析器
from nfo_parser_fixed import FixedNFOParser as NFOParser


class MarkdownGenerator:
    """Markdown文件生成器"""

    def __init__(self, config: Config):
        self.config = config
        self.output_dir = Path(config.get('paths.output_directory', 'obsidian_output'))
        self.template = self.load_template()
        self.nfo_parser = NFOParser(config)

    def load_template(self) -> str:
        """加载Markdown模板 - 基于SONE-752.md的展示样式"""
        template = """---
cssclasses:
  - film-page
CN: {title_cn}
JP: {title_jp}
Code: {code}
Actor:
{actor_data}
Year: {year}
Time: {duration}
VideoRank: {rating}
Series:
{series_data}
Keywords:
{keywords_data}
Cover: {cover_path}
Fanart: {fanart_path}
---

```dataviewjs
/********** 基础配置 **********/
const ROOT = "{root_dir}";
const GALLERY_CANDIDATES = [`${{ROOT}}/gallery`, `gallery`];
const YEAR_LINK_DIR   = "{years_directory}";
const RANK_LINK_DIR   = "{ranks_directory}";
const SERIES_LINK_DIR = "{series_directory}";
const ACTOR_LINK_DIR  = "jav_store/actor";
const KW_DIR          = "{keywords_directory}";   // 关键词目录，集中到jav_store/keywords

/********** 工具：解析文件 / 生成内部链接（不依赖 fileToLinktext） **********/
function resolveFile(anyPathLike, base){{
  if (!anyPathLike) return null;
  if (typeof anyPathLike === "string"){{
    const s = anyPathLike.trim();
    const m = s.match(/^\\[\\[([^\\\\]#|]+)(?:#[^\\\\]|]+)?(?:\\\\|[^\\]]+)?\\]\\]$/);
    if (m) return app.metadataCache.getFirstLinkpathDest(m[1], base);

    // 处理相对路径和绝对路径
    let targetPath = s;
    // 如果是相对路径（以../开头），需要转换为从vault根目录的路径
    if (s.startsWith('../')) {{
      // 获取当前文件的目录
      const currentFile = base || dv.current().file.path;
      const currentDir = currentFile.substring(0, currentFile.lastIndexOf('/'));
      // 移除../并构建从vault根目录的路径
      targetPath = currentDir.replace(/\\/[^/]+$/, '') + '/' + s.replace(/^\\.\\.\\//, '');
    }}

    return app.vault.getAbstractFileByPath(targetPath)
        ?? app.metadataCache.getFirstLinkpathDest(targetPath, base);
  }}
  if (anyPathLike?.path){{
    return app.vault.getAbstractFileByPath(anyPathLike.path)
        ?? app.metadataCache.getFirstLinkpathDest(anyPathLike.path, base);
  }}
  return null;
}}
function makeILink(targetPathOrName, label, sourcePath){{
  const t = String(targetPathOrName ?? "").trim();
  const src = sourcePath ?? dv.current().file.path;
  const dest = app.metadataCache.getFirstLinkpathDest(t, src);
  const a = document.createElement('a');
  a.classList.add('internal-link');
  const href = dest ? dest.path : t;
  a.setAttribute('href', href);
  a.setAttribute('data-href', href);
  a.textContent = label ?? (dest ? dest.basename : t);
  return a;
}}
// 包一层"浮起"徽章
function chipLink(target, label, src){{
  const span = document.createElement('span'); span.className = 'chip';
  span.appendChild(makeILink(target, label, src));
  return span;
}}
// 展开 - - - 这种嵌套数组
function flattenDeep(x){{
  if (Array.isArray(x)) return x.reduce((a,v)=>a.concat(flattenDeep(v)), []);
  if (typeof x === "string" || x?.path) return [x];
  return [];
}}

/********** 页面元素 **********/
const me = dv.current();
const el = dv.container;

/*** 信息（最上面） ***/
const infoSec = document.createElement('section');
infoSec.className = 'film-info film-info--top';
const ul = document.createElement('ul'); ul.className = 'info-list';

// 演员 → 徽章 + 内链（支持多个演员）
{{
  const actors = me.Actor ? String(me.Actor).split(',').map(a => a.trim()).filter(Boolean) : [];
  if (actors.length){{
    const li = document.createElement('li');
    li.innerHTML = `<span class="k">演员</span><span class="v"><div class="kw-badges"></div></span>`;
    const box = li.querySelector('.kw-badges');
    for (const actor of actors){{
      const actorPath = ACTOR_LINK_DIR ? `${{ACTOR_LINK_DIR}}/${{actor}}` : actor;
      const badge = chipLink(actorPath, actor, me.file.path);
      box.appendChild(badge);
    }}
    ul.appendChild(li);
  }}
}}
// 年份 → years/2025
if (me.Year){{
  const li = document.createElement('li');
  li.innerHTML = `<span class="k">年份</span><span class="v"></span>`;
  const target = YEAR_LINK_DIR ? `${{YEAR_LINK_DIR}}/${{me.Year}}` : `${{me.Year}}`;
  li.querySelector('.v').appendChild(chipLink(target, String(me.Year), me.file.path));
  ul.appendChild(li);
}}
// 系列（支持字符串 / [[链接]] / 列表）
{{
  const raw = (me.Series ?? me.series);
  const arr  = Array.isArray(raw) ? raw : (raw ? [raw] : []);
  if (arr.length){{
    const li = document.createElement('li');
    li.innerHTML = `<span class="k">系列</span><span class="v"><div class="kw-badges"></div></span>`;
    const box = li.querySelector('.kw-badges');
    for (const one of arr){{
      let target, label;
      if (one?.path){{ target=one.path; label=one.display ?? one.path.split('/').pop(); }}
      else {{
        const s = String(one).trim();
        const m = s.match(/^\\[\\[([^\\]#|]+)(?:#[^\\]|]+)?(?:\\|([^\\]]+))?\\]\\]$/);
        if (m){{ target=m[1]; label=m[2] ?? m[1].split('/').pop(); }}
        else {{ target = SERIES_LINK_DIR ? `${{SERIES_LINK_DIR}}/${{s}}` : s; label = s; }}
      }}
      const badge = document.createElement('span'); badge.className='chip';
      badge.appendChild(makeILink(target, label, me.file.path));
      box.appendChild(badge);
    }}
    ul.appendChild(li);
  }}
}}
// 评分 → ranks/5
if (me.VideoRank !== undefined && me.VideoRank !== null && String(me.VideoRank)!==""){{
  const li = document.createElement('li');
  li.innerHTML = `<span class="k">评分</span><span class="v"></span>`;
  const target = RANK_LINK_DIR ? `${{RANK_LINK_DIR}}/${{me.VideoRank}}` : `${{me.VideoRank}}`;
  li.querySelector('.v').appendChild(chipLink(target, String(me.VideoRank), me.file.path));
  ul.appendChild(li);
}}
// 关键词 → 徽章
{{
  const terms = flattenDeep(me.Keywords ?? [])
    .map(k => k?.path ? k.path : String(k).trim()).filter(Boolean);
  const li = document.createElement('li');
  li.innerHTML = `<span class="k">关键词</span><span class="v"><div class="kw-badges"></div></span>`;
  const box = li.querySelector('.kw-badges');
  for (const t of terms){{
    const m = t.match(/^\\[\\[([^\\]#|]+)(?:#[^\\]|]+)?(?:\\|([^\\]]+))?\\]\\]$/);
    const target = m ? m[1] : (KW_DIR ? `${{KW_DIR}}/${{t}}` : t);
    const label  = m ? (m[2] ?? m[1].split('/').pop()) : t;
    const badge  = document.createElement('span'); badge.className='chip';
    badge.appendChild(makeILink(target, label, me.file.path));
    box.appendChild(badge);
  }}
  ul.appendChild(li);
}}
infoSec.innerHTML = `<h3 class="sec-title">🛈 影片信息</h3>`;
infoSec.appendChild(ul);
el.appendChild(infoSec);

/*** 封面（独占一行） ***/
{{
  const coverFile = resolveFile(me.Cover, me.file.path);
  if (coverFile) {{
    const coverSec = document.createElement('section');
    coverSec.className = 'film-cover-full';
    coverSec.innerHTML = `<img src="${{app.vault.adapter.getResourcePath(coverFile.path)}}" class="film-cover-full__img" alt="Cover">`;
    el.appendChild(coverSec);
  }}
  // 如果没有cover文件，不显示任何内容
}}

/*** 九宫格预览 ***/
function getGalleryPaths(code){{
  if (!code) return [];

  // 生成可能的目录名称变体
  const getDirectoryVariants = (baseCode) => {{
    const variants = [baseCode];

    // 如果以数字结尾，尝试添加-C后缀
    if (/\\d+$/.test(baseCode)) {{
      variants.push(baseCode + '-C');
    }}

    // 如果已经以-C结尾，也尝试不带-C的版本
    if (baseCode.endsWith('-C')) {{
      variants.push(baseCode.slice(0, -2));
    }}

    return variants;
  }};

{preview_patterns_js}

  // 尝试所有可能的目录名称变体
  const directoryVariants = getDirectoryVariants(code);

  for (const pattern of patterns) {{
    for (const base of pattern.base_dirs) {{
      for (const dirVariant of directoryVariants) {{
        const paths = pattern.filename_pattern.map(filename =>
          pattern.path_template(base, dirVariant, filename)
        );
        const files = paths.map(p => app.vault.getAbstractFileByPath(p)).filter(Boolean);
        if (files.length) {{
          return files.map(f => f.path);
        }}
      }}
    }}
  }}

  return [];
}}
const gifPaths = getGalleryPaths(me.Code);
const pv = document.createElement('section'); pv.className = 'film-preview';
pv.innerHTML = `<h3 class="sec-title">🎞 影片预览</h3>`;
const grid = document.createElement('div'); grid.className = 'pv-grid';

// 如果没有找到预设的预览图，尝试查找extrafanart目录中的实际文件
let previewPaths = gifPaths;
if (!previewPaths || previewPaths.length === 0) {{
  const code = me.Code;
  const baseDirs = ['jav_store/source'];

  // 生成可能的目录名称变体
  const getDirectoryVariants = (baseCode) => {{
    const variants = [baseCode];

    // 如果以数字结尾，尝试添加-C后缀
    if (/\\d+$/.test(baseCode)) {{
      variants.push(baseCode + '-C');
    }}

    // 如果已经以-C结尾，也尝试不带-C的版本
    if (baseCode.endsWith('-C')) {{
      variants.push(baseCode.slice(0, -2));
    }}

    return variants;
  }};

  const directoryVariants = getDirectoryVariants(code);

  for (const baseDir of baseDirs) {{
    // 尝试所有可能的目录名称变体
    for (const dirVariant of directoryVariants) {{
      const fanartDir = `${{baseDir}}/${{dirVariant}}/extrafanart`;
      const fanartFolder = app.vault.getAbstractFileByPath(fanartDir);

      if (fanartFolder && fanartFolder.children) {{
        // 优先查找GIF文件，然后查找JPG文件
        const fanartPaths = fanartFolder.children
          .filter(f => f.name.match(/\\\\.gif$/i) || f.name.match(/fanart.*\\\\.jpg$/i))
          .sort((a, b) => {{
            // GIF文件优先
            const aIsGif = a.name.match(/\\\\.gif$/i);
            const bIsGif = b.name.match(/\\\\.gif$/i);
            if (aIsGif && !bIsGif) return -1;
            if (!aIsGif && bIsGif) return 1;
            // 同类型按文件名排序
            return a.name.localeCompare(b.name);
          }})
          .map(f => f.path);

        if (fanartPaths.length > 0) {{
          previewPaths = fanartPaths;
          break;
        }}
      }}

      // 如果extrafanart目录不存在，尝试查找基础目录中的fanart文件
      const basePath = `${{baseDir}}/${{dirVariant}}`;
      const codeFolder = app.vault.getAbstractFileByPath(basePath);
      if (codeFolder && codeFolder.children) {{
        const basePreviewPaths = codeFolder.children
          .filter(f => f.name.match(new RegExp(`${{dirVariant}}.*-(poster|fanart|thumb)\\\\.(jpg|png|gif)$`, 'i')) || f.name.match(/-(poster|fanart|thumb)\\\\.(jpg|png|gif)$/i))
          .map(f => f.path);
        if (basePreviewPaths.length > 0) {{
          previewPaths = basePreviewPaths;
          break;
        }}
      }}
    }}

    // 如果找到了预览图，跳出外层循环
    if (previewPaths.length > 0) break;
  }}
}}

grid.innerHTML = previewPaths && previewPaths.length > 0
  ? previewPaths.map(p => `<img loading="lazy" class="pv-img" src="${{app.vault.adapter.getResourcePath(p)}}">`).join("")
  : `<div class="empty">未找到预览图（尝试了画廊目录和extrafanart目录）</div>`;
pv.appendChild(grid);
el.appendChild(pv);
```

{trailer_section}

{play_button_section}

```dataviewjs
/*** 正文占位 ***/
dv.header(2, "📖 故事简介");
dv.paragraph("> {plot_summary}");
dv.header(2, "🗒️ 备注");
dv.paragraph("> {additional_note}");
```
"""
        return template

    def generate_markdown(self, media_info: MediaInfo) -> str:
        """生成Markdown内容 - 基于SONE-752.md样式"""

        # 解析NFO文件
        nfo_data = {}
        if media_info.nfo_path and os.path.exists(media_info.nfo_path):
            nfo_data = self.nfo_parser.parse_nfo(media_info.nfo_path)

        # 获取配置
        path_mode = self.config.get('markdown.links.path_mode', 'absolute')
        absolute_path_prefix = self.config.get('markdown.links.absolute_path_prefix', '')

        def format_media_path(file_path: str) -> str:
            """格式化媒体文件路径为从jav_store开始的相对路径"""
            if not file_path:
                return ""

            # 获取绝对路径
            abs_path = os.path.abspath(file_path)

            # 如果配置了绝对路径前缀，移除它
            if absolute_path_prefix and abs_path.startswith(absolute_path_prefix):
                relative = abs_path.replace(absolute_path_prefix, '').lstrip('/\\')
            else:
                relative = abs_path

            # 标准化路径分隔符
            relative = relative.replace('\\', '/')

            # 如果路径不以"jav_store"开头，添加它
            if not relative.startswith('jav_store'):
                # 如果路径包含jav_store，从jav_store开始截取
                if 'jav_store' in relative:
                    # 找到jav_store在路径中的位置
                    jav_index = relative.find('jav_store')
                    relative = relative[jav_index:]
                else:
                    # 如果不包含jav_store，假设它在source下
                    relative = 'jav_store/source/' + relative

            return relative

        # 处理演员信息
        actors = nfo_data.get('actors', media_info.actors)
        # 支持多个演员显示
        if actors and len(actors) > 1:
            actor_str = ", ".join(actors)  # 多个演员用逗号分隔
        elif actors and len(actors) == 1:
            actor_str = actors[0]
        else:
            actor_str = "未知演员"

        # 处理标题 - CN对应title，JP对应originaltitle
        title_cn = nfo_data.get('title', media_info.code)
        title_jp = nfo_data.get('originaltitle', title_cn)  # 如果没有originaltitle，使用title作为备用

        # 提取年份
        release_date = nfo_data.get('release_date', '')
        year = self._extract_year_from_date(release_date) if release_date else "未知"

        # 时长（从NFO的runtime字段获取）
        duration = nfo_data.get('runtime', '170')  # 从NFO获取runtime，默认170分钟

        # 处理系列数据
        series = nfo_data.get('series', '')
        if series:
            # 使用YAML数组格式，类似SONE-752.md中的格式
            # 转义Windows路径中的反斜杠和特殊字符
            series_escaped = series.replace('\\', '\\\\').replace('"', '\\"')
            series_data = f"  - - {series_escaped}"
        else:
            series_data = "  - []"

        # 处理关键词数据
        genres = nfo_data.get('genre', media_info.genre)
        keywords_data = self._format_keywords(genres)

        # 处理封面路径
        cover_path = ""
        if media_info.poster_path:
            # 使用配置的路径模式格式化路径
            cover_path = format_media_path(media_info.poster_path)
        else:
            cover_path = ""  # 留空，让dataviewjs脚本处理"No Cover"情况

        # 生成trailer播放器部分
        trailer_section = self._generate_trailer_section(media_info, nfo_data)

        # 生成播放按钮部分
        play_button_section = self._generate_play_button_section(media_info, nfo_data)

        # 处理剧情简介
        plot_default = self.nfo_parser.defaults.get('plot', '暂无该部分信息')
        plot = nfo_data.get('plot', plot_default)
        if not plot.strip():
            plot = plot_default

        # 生成文件创建时间
        datetime_format = self.config.get('basic.datetime_format', "%Y-%m-%d %H:%M:%S")
        creation_time = datetime.now().strftime(datetime_format)
        additional_note = f"文件生成时间: {creation_time}"

        # 获取根目录配置
        root_dir = self.config.get('dataview.root_dir', 'jav_store/source')
        years_directory = self.config.get('dataview.years_directory', 'jav_store/years')
        ranks_directory = self.config.get('dataview.ranks_directory', 'jav_store/ranks')
        series_directory = self.config.get('dataview.series_directory', 'jav_store/series')
        keywords_directory = self.config.get('dataview.keywords_directory', '')

        # 填充新模板
        template_data = {
            'title_cn': title_cn,
            'title_jp': title_jp,
            'code': media_info.code,
            'actor_data': self._format_actors(actors),
            'year': year,
            'duration': duration,
            'rating': round(nfo_data.get('rating', 0), 1),
            'series_data': series_data,
            'keywords_data': keywords_data,
            'cover_path': cover_path,
            'fanart_path': format_media_path(media_info.fanart_path) if media_info.fanart_path else "",
            'root_dir': root_dir,
            'years_directory': years_directory,
            'ranks_directory': ranks_directory,
            'series_directory': series_directory,
            'keywords_directory': keywords_directory,
            'trailer_section': trailer_section,
            'play_button_section': play_button_section,
            'preview_patterns_js': self._generate_preview_patterns_js(),
            'plot_summary': plot,
            'additional_note': additional_note  # 文件生成时间
        }

        content = self.template.format(**template_data)

        return content

    def _extract_year_from_date(self, date_str: str) -> str:
        """从日期字符串中提取年份"""
        import re
        # 匹配四种年份格式: 2025, 2025-01-01, 01/01/2025, 2025年01月01日
        year_match = re.search(r'(\d{4})', date_str)
        return year_match.group(1) if year_match else "未知"

    def _format_keywords(self, genres: List[str]) -> str:
        """格式化关键词为YAML数组格式"""
        if not genres:
            return "[]"

        # 过滤关键词
        filtering_config = self.config.get('filtering', {})
        exclude_keywords = filtering_config.get('exclude_keywords', [])

        filtered_genres = []
        for genre in genres:
            should_exclude = False
            for keyword in exclude_keywords:
                if keyword in genre:
                    should_exclude = True
                    break
            if not should_exclude:
                filtered_genres.append(genre)

        if not filtered_genres:
            return "[]"

        # 获取最大关键词数量配置，设置为更大的值以包含所有关键词
        max_keywords = self.config.get('content.max_keywords', 20)

        # 格式化为YAML数组，类似SONE-752.md中的格式
        if not filtered_genres:
            return "  - []"

        keyword_lines = []
        for genre in filtered_genres[:max_keywords]:  # 使用配置的最大关键词数量
            # 转义特殊字符
            genre_escaped = genre.replace('\\', '\\\\').replace('"', '\\"')
            keyword_lines.append(f"  - - - {genre_escaped}")

        return "\n".join(keyword_lines)

    def _format_actors(self, actors: List[str]) -> str:
        """格式化演员为YAML数组格式，类似关键词格式"""
        if not actors:
            return "  - []"
        actor_lines = []
        for actor in actors:
            # 转义特殊字符
            actor_escaped = actor.replace('\\', '\\\\').replace('"', '\\"')
            actor_lines.append(f"  - - - {actor_escaped}")
        return "\n".join(actor_lines)

    def _generate_preview_patterns_js(self) -> str:
        """生成预览图模式的JavaScript配置"""
        preview_patterns = self.config.get('dataview.preview_patterns', [])

        if not preview_patterns:
            # 如果没有配置，使用默认配置
            return '''  // 默认预览图模式
  const patterns = [
    // 模式1: 标准的1-9.gif格式（支持gallery和extrafanart目录）
    {
      base_dirs: [...GALLERY_CANDIDATES, "jav_store/source"],
      filename_pattern: Array.from({length:9}, (_,i)=>`${i+1}.gif`),
      path_template: (base, code, filename) => {
        // 如果是jav_store/source，则查找extrafanart目录
        if (base.includes("jav_store/source")) {
          return `${base}/${code}/extrafanart/${filename}`;
        }
        return `${base}/${code}/${filename}`;
      }
    },
    // 模式2: extrafanart目录的fanart1-12.jpg格式
    {
      base_dirs: ["{root_dir}", "jav_store/source"],
      filename_pattern: Array.from({length:12}, (_,i)=>`fanart${i+1}.jpg`),
      path_template: (base, code, filename) => `${base}/${code}/extrafanart/${filename}`
    }
  ];'''

        # 生成JavaScript代码
        js_lines = ["  // 预览图模式配置 (来自config.yaml)"]
        js_lines.append("  const patterns = [")

        for i, pattern in enumerate(preview_patterns):
            name = pattern.get('name', f'模式{i+1}')
            base_dirs = pattern.get('base_dirs', [])
            filename_pattern = pattern.get('filename_pattern', '1-9.jpg')
            path_template = pattern.get('path_template', '${base}/${code}/${filename}')

            js_lines.append(f"    // {name}")

            # 解析文件名模式
            if '-' in filename_pattern:
                # 例如: "1-9.gif" 或 "fanart1-12.jpg"
                parts = filename_pattern.split('-')
                if len(parts) == 2:
                    prefix = parts[0].rstrip('1234567890')
                    start = int(''.join([c for c in parts[0] if c.isdigit()]) or '1')
                    end = int(''.join([c for c in parts[1] if c.isdigit()]) or '9')
                    suffix = parts[1].lstrip('1234567890')

                    js_lines.append(f"    {{")
                    js_lines.append(f"      base_dirs: {base_dirs},")
                    js_lines.append(f"      filename_pattern: Array.from({{length:{end-start+1}}}, (_,i)=>`{prefix}${{i+{start}}}{suffix}`),")
                    js_lines.append(f"      path_template: (base, code, filename) => `{path_template}`")
                    js_lines.append(f"    }},")
                else:
                    # 单个文件
                    js_lines.append(f"    {{")
                    js_lines.append(f"      base_dirs: {base_dirs},")
                    js_lines.append(f"      filename_pattern: ['{filename_pattern}'],")
                    js_lines.append(f"      path_template: (base, code, filename) => `{path_template}`")
                    js_lines.append(f"    }},")
            else:
                # 单个文件
                js_lines.append(f"    {{")
                js_lines.append(f"      base_dirs: {base_dirs},")
                js_lines.append(f"      filename_pattern: ['{filename_pattern}'],")
                js_lines.append(f"      path_template: (base, code, filename) => `{path_template}`")
                js_lines.append(f"    }},")

        js_lines.append("  ];")
        return "\n".join(js_lines)

    def _generate_trailer_section(self, media_info: MediaInfo, nfo_data: dict) -> str:
        """生成trailer播放器部分 - 使用简单的markdown链接形式"""
        if not media_info.trailer_path:
            return ""

        # 检查trailer文件是否存在
        trailer_path = media_info.trailer_path
        if not os.path.exists(trailer_path):
            logging.warning(f"Trailer文件不存在: {trailer_path}")
            return ""

        # 检查trailer文件大小，如果小于配置的最小值则不显示
        try:
            file_size = os.path.getsize(trailer_path)
            # 从配置文件获取最小trailer文件大小，默认500KB
            min_size = self.config.get('advanced.file_size_limits.min_trailer_size', 500 * 1024)
            min_size_kb = min_size / 1024  # 转换为KB用于日志显示
            if file_size < min_size:
                file_size_kb = file_size / 1024
                logging.info(f"Trailer文件过小，跳过显示: {trailer_path} ({file_size_kb:.1f}KB < {min_size_kb:.0f}KB)")
                return ""
        except OSError as e:
            logging.warning(f"无法获取trailer文件大小: {trailer_path} - {e}")
            return ""

        # 获取trailer文件的绝对路径
        trailer_abs_path = os.path.abspath(trailer_path)
        # 格式化为从vault根目录的相对路径
        trailer_vault_path = self._format_media_path_for_trailer(trailer_path)
        trailer_filename = os.path.basename(trailer_path)

        return f'''## 🎥 预告片

![[{trailer_filename}]]

'''

    def _format_media_path_for_trailer(self, file_path: str) -> str:
        """格式化媒体文件路径为trailer显示用的相对路径"""
        if not file_path:
            return ""

        # 获取绝对路径
        abs_path = os.path.abspath(file_path)

        # 获取配置的绝对路径前缀
        absolute_path_prefix = self.config.get('markdown.links.absolute_path_prefix', '')

        # 如果配置了绝对路径前缀，移除它
        if absolute_path_prefix and abs_path.startswith(absolute_path_prefix):
            relative = abs_path.replace(absolute_path_prefix, '').lstrip('/\\')
        else:
            relative = abs_path

        # 标准化路径分隔符
        relative = relative.replace('\\', '/')

        # 如果路径不以"jav_store"开头，添加它
        if not relative.startswith('jav_store'):
            # 如果路径包含jav_store，从jav_store开始截取
            if 'jav_store' in relative:
                # 找到jav_store在路径中的位置
                jav_index = relative.find('jav_store')
                relative = relative[jav_index:]
            else:
                # 如果不包含jav_store，假设它在source下
                relative = 'jav_store/source/' + relative

        return relative

    def _generate_play_button_section(self, media_info: MediaInfo, nfo_data: dict) -> str:
        """生成播放模块部分"""
        if not media_info.video_path:
            return ""

        # 添加大标题
        title_section = f"\n## 🎬 正片\n\n"

        if media_info.video_path.endswith('.strm'):
            # STRM文件的播放按钮
            play_section = self._generate_strm_play_section(media_info.video_path, media_info.code)
        else:
            # 所有格式(包括MP4)都使用传统播放按钮方式
            play_section = self._generate_local_play_button(media_info.video_path)

        return title_section + play_section

    def _generate_strm_play_section(self, strm_path: str, media_code: str) -> str:
        """生成STRM文件播放模块"""
        try:
            with open(strm_path, 'r', encoding='utf-8') as f:
                strm_url = f.read().strip()
        except Exception as e:
            logging.warning(f"无法读取STRM文件 {strm_path}: {e}")
            return ""

        return f'''```meta-bind-button
label: PLAY
style: primary
icon: play
class: btn-001
action:
  type: inlineJS
  code: |
    // STRM文件播放链接 - {media_code}
    const strmUrl = "{strm_url}";
    // 用 Electron 直接让系统默认播放器打开
    require('electron').shell.openPath(strmUrl);

```'''

    def _generate_local_play_button(self, video_path: str) -> str:
        """生成本地视频文件播放按钮（用于MP4, MKV, AVI, MOV, WMV等所有本地格式）"""
        abs_path = os.path.abspath(video_path)
        # 格式化为Electron兼容路径
        electron_path = abs_path.replace('\\', '/')

        return f'''```meta-bind-button
label: PLAY
style: primary
icon: play
class: btn-001
action:
  type: inlineJS
  code: |
    // 本地视频文件播放
    const p = "{electron_path}";
    // 用 Electron 直接让系统默认播放器打开
    require('electron').shell.openPath(p);

```'''

    
    def save_markdown(self, media_info: MediaInfo, content: str):
        """保存Markdown文件，确保使用基础番号作为文件名"""
        # 确保文件名是基础番号，不包含后缀
        base_code = media_info.code
        # 如果番号包含后缀，提取基础部分
        if '-' in base_code and len(base_code.split('-')) > 2:
            # 例如: EDRG-009-F -> EDRG-009
            parts = base_code.split('-')
            base_code = f"{parts[0]}-{parts[1]}"

        filename = f"{base_code}.md"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        logging.info(f"已生成Markdown文件: {filepath}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='媒体收集器 - 生成Obsidian笔记')
    parser.add_argument('--config', '-c', default='config.yaml',
                       help='配置文件路径 (默认: config.yaml)')
    parser.add_argument('--source-dir', help='源媒体文件目录 (覆盖配置文件设置)')
    parser.add_argument('--output-dir', help='输出Markdown文件目录 (覆盖配置文件设置)')

    args = parser.parse_args()

    try:
        # 加载配置
        config = Config(args.config)

        # 重新设置日志级别（确保命令行参数覆盖后生效）
        log_level = config.config.get('advanced', {}).get('log_level', 'INFO')
        logging.getLogger().setLevel(getattr(logging, log_level))

        # 命令行参数覆盖配置文件
        if args.source_dir:
            config.config['paths']['source_directories'] = [args.source_dir]
        if args.output_dir:
            config.config['paths']['output_directory'] = args.output_dir

        logging.info("开始扫描媒体文件...")

        # 创建扫描器
        scanner = MediaScanner(config)

        # 扫描文件
        media_groups = scanner.scan_directory()

        if not media_groups:
            logging.warning("未找到任何媒体文件")
            return

        logging.info(f"发现 {len(media_groups)} 个媒体项目")

        # 创建生成器
        generator = MarkdownGenerator(config)

        # 生成Markdown文件
        for code, media_info in media_groups.items():
            logging.info(f"正在处理: {code}")
            content = generator.generate_markdown(media_info)
            generator.save_markdown(media_info, content)

        # 生成演员页面
        logging.info("开始生成演员页面...")
        actor_generator = ActorPageGenerator(config)
        actor_generator.generate_actor_pages(media_groups)

        # 生成分类页面
        logging.info("开始生成分类页面...")
        category_generator = CategoryPageGenerator(config)
        category_generator.generate_all_category_pages(media_groups)

        # 使用独立的分类页面生成器
        logging.info("开始使用独立分类生成器生成页面...")
        independent_generator = IndependentCategoryGenerator(config)

        # 生成各类独立页面
        independent_generator.generate_all_actor_pages()
        independent_generator.generate_all_keywords_pages()
        independent_generator.generate_all_ranks_pages()
        independent_generator.generate_all_series_pages()
        independent_generator.generate_all_years_pages()

        output_dir = config.get('paths.output_directory', 'obsidian_output')
        logging.info(f"完成! 已生成 {len(media_groups)} 个Markdown文件到: {output_dir}")

    except Exception as e:
        logging.error(f"程序执行失败: {e}")
        raise


class IndependentCategoryGenerator:
    """独立的分类页面生成器 - 基于films文件夹的MD文件内容生成分类页面"""

    def __init__(self, config: Config):
        self.config = config
        self.base_dir = Path(config.get('paths.output_directory', 'jav_store')).parent
        self.films_dir = self.base_dir / 'films'

    def generate_all_actor_pages(self):
        """读取films文件夹中的Actor属性，为每个演员生成页面"""
        logging.info("开始独立生成演员页面...")

        # 收集所有演员及其作品
        actor_works = {}

        # 扫描films文件夹中的所有MD文件
        for md_file in self.films_dir.glob('*.md'):
            try:
                # 读取MD文件的frontmatter
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 提取frontmatter
                if content.startswith('---'):
                    frontmatter_end = content.find('---', 3)
                    if frontmatter_end > 0:
                        frontmatter_text = content[3:frontmatter_end]
                        actor_data = self._extract_actor_from_frontmatter(frontmatter_text)

                        if actor_data:
                            for actor in actor_data:
                                if actor and actor not in ["", "未知", None]:
                                    if actor not in actor_works:
                                        actor_works[actor] = []
                                    actor_works[actor].append(md_file.stem)

            except Exception as e:
                logging.warning(f"处理文件 {md_file} 时出错: {e}")

        # 为每个演员生成页面
        actor_dir = self.base_dir / 'actor'
        actor_dir.mkdir(exist_ok=True)

        for actor, works in actor_works.items():
            self._generate_actor_page(actor, works)

        logging.info(f"已生成 {len(actor_works)} 个演员页面")

    def generate_all_keywords_pages(self):
        """读取films文件夹中的Keywords属性，为每个关键词生成页面"""
        logging.info("开始独立生成关键词页面...")

        keyword_works = {}

        for md_file in self.films_dir.glob('*.md'):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if content.startswith('---'):
                    frontmatter_end = content.find('---', 3)
                    if frontmatter_end > 0:
                        frontmatter_text = content[3:frontmatter_end]
                        keywords_data = self._extract_keywords_from_frontmatter(frontmatter_text)

                        if keywords_data:
                            for keyword in keywords_data:
                                if keyword and keyword not in ["", "未知", None]:
                                    if keyword not in keyword_works:
                                        keyword_works[keyword] = []
                                    keyword_works[keyword].append(md_file.stem)

            except Exception as e:
                logging.warning(f"处理文件 {md_file} 时出错: {e}")

        # 只为有作品的关键词生成页面
        valid_keyword_works = {k: v for k, v in keyword_works.items() if len(v) > 0}

        keywords_dir = self.base_dir / 'keywords'
        keywords_dir.mkdir(exist_ok=True)

        for keyword, works in valid_keyword_works.items():
            self._generate_keywords_page(keyword, works)

        logging.info(f"已生成 {len(valid_keyword_works)} 个关键词页面")

    def generate_all_ranks_pages(self):
        """读取films文件夹中的VideoRank属性，为每个评分生成页面"""
        logging.info("开始独立生成评分页面...")

        rank_works = {}

        for md_file in self.films_dir.glob('*.md'):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if content.startswith('---'):
                    frontmatter_end = content.find('---', 3)
                    if frontmatter_end > 0:
                        frontmatter_text = content[3:frontmatter_end]
                        rank_data = self._extract_rank_from_frontmatter(frontmatter_text)

                        if rank_data and rank_data not in ["", "未知", None]:
                            if rank_data not in rank_works:
                                rank_works[rank_data] = []
                            rank_works[rank_data].append(md_file.stem)

            except Exception as e:
                logging.warning(f"处理文件 {md_file} 时出错: {e}")

        ranks_dir = self.base_dir / 'ranks'
        ranks_dir.mkdir(exist_ok=True)

        for rank, works in rank_works.items():
            self._generate_rank_page(rank, works)

        logging.info(f"已生成 {len(rank_works)} 个评分页面")

    def generate_all_series_pages(self):
        """读取films文件夹中的Series属性，为每个系列生成页面"""
        logging.info("开始独立生成系列页面...")

        series_works = {}

        for md_file in self.films_dir.glob('*.md'):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if content.startswith('---'):
                    frontmatter_end = content.find('---', 3)
                    if frontmatter_end > 0:
                        frontmatter_text = content[3:frontmatter_end]
                        series_data = self._extract_series_from_frontmatter(frontmatter_text)

                        if series_data:
                            for series in series_data:
                                if series and series not in ["", "未知", None]:
                                    if series not in series_works:
                                        series_works[series] = []
                                    series_works[series].append(md_file.stem)

            except Exception as e:
                logging.warning(f"处理文件 {md_file} 时出错: {e}")

        series_dir = self.base_dir / 'series'
        series_dir.mkdir(exist_ok=True)

        for series, works in series_works.items():
            self._generate_series_page(series, works)

        logging.info(f"已生成 {len(series_works)} 个系列页面")

    def generate_all_years_pages(self):
        """读取films文件夹中的Year属性，为每个年份生成页面"""
        logging.info("开始独立生成年份页面...")

        year_works = {}

        for md_file in self.films_dir.glob('*.md'):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if content.startswith('---'):
                    frontmatter_end = content.find('---', 3)
                    if frontmatter_end > 0:
                        frontmatter_text = content[3:frontmatter_end]
                        year_data = self._extract_year_from_frontmatter(frontmatter_text)

                        if year_data and year_data not in ["", "未知", None]:
                            if year_data not in year_works:
                                year_works[year_data] = []
                            year_works[year_data].append(md_file.stem)

            except Exception as e:
                logging.warning(f"处理文件 {md_file} 时出错: {e}")

        years_dir = self.base_dir / 'years'
        years_dir.mkdir(exist_ok=True)

        for year, works in year_works.items():
            self._generate_year_page(year, works)

        logging.info(f"已生成 {len(year_works)} 个年份页面")

    def _extract_actor_from_frontmatter(self, frontmatter_text: str) -> List[str]:
        """从frontmatter中提取Actor属性"""
        actors = []
        found_actor_section = False

        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if line.startswith('Actor:'):
                found_actor_section = True
                # 处理单行格式：Actor: actor_name
                actor_name = line.replace('Actor:', '').strip()
                if actor_name and actor_name not in ['-', '[]']:
                    actors.append(actor_name)
            elif found_actor_section and line.startswith('- - -'):
                # 处理嵌套数组格式：- - - actor_name
                actor_name = line.replace('- - -', '').strip()
                if actor_name:
                    actors.append(actor_name)
            elif found_actor_section and not line.startswith('-') and line and ':' in line:
                # 遇到新的字段，结束Actor解析
                found_actor_section = False

        return actors

    def _extract_keywords_from_frontmatter(self, frontmatter_text: str) -> List[str]:
        """从frontmatter中提取Keywords属性"""
        keywords = []
        found_keywords_section = False

        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if line.startswith('Keywords:'):
                found_keywords_section = True
                # 处理单行格式：Keywords: keyword_name
                keyword_name = line.replace('Keywords:', '').strip()
                if keyword_name and keyword_name not in ['-', '[]']:
                    keywords.append(keyword_name)
            elif found_keywords_section and line.startswith('- - -'):
                # 处理嵌套数组格式：- - - keyword_name
                keyword_name = line.replace('- - -', '').strip()
                if keyword_name:
                    keywords.append(keyword_name)
            elif found_keywords_section and not line.startswith('-') and line and ':' in line:
                # 遇到新的字段，结束Keywords解析
                found_keywords_section = False

        return keywords

    def _extract_rank_from_frontmatter(self, frontmatter_text: str) -> str:
        """从frontmatter中提取VideoRank属性，并统一格式化为一位小数"""
        for line in frontmatter_text.split('\n'):
            if line.strip().startswith('VideoRank:'):
                rank_str = line.replace('VideoRank:', '').strip()
                try:
                    rank = float(rank_str)
                    # 统一格式化为一位小数
                    return str(round(rank, 1))
                except ValueError:
                    return rank_str
        return ""

    def _extract_series_from_frontmatter(self, frontmatter_text: str) -> List[str]:
        """从frontmatter中提取Series属性"""
        series_list = []
        found_series_section = False

        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if line.startswith('Series:'):
                found_series_section = True
                # 处理单行格式：Series: series_name
                series_name = line.replace('Series:', '').strip()
                if series_name and series_name not in ['-', '[]']:
                    series_list.append(series_name)
            elif found_series_section and (line.startswith('- - -') or line.startswith('- -')):
                # 处理嵌套数组格式：- - - series_name 或 - - series_name
                series_name = line.replace('- - -', '').replace('- -', '').strip()
                if series_name:
                    series_list.append(series_name)
            elif found_series_section and not line.startswith('-') and line and ':' in line:
                # 遇到新的字段，结束Series解析
                found_series_section = False

        return series_list

    def _extract_year_from_frontmatter(self, frontmatter_text: str) -> str:
        """从frontmatter中提取Year属性"""
        for line in frontmatter_text.split('\n'):
            if line.strip().startswith('Year:'):
                year = line.replace('Year:', '').strip()
                return year
        return ""

    def _generate_actor_page(self, actor: str, works: List[str]):
        """生成演员页面"""
        actor_file = self.base_dir / 'actor' / f"{actor}.md"
        content = self._generate_preview_style_page('actor', actor, works)

        with open(actor_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"已生成演员页面: {actor_file}")

    def _generate_keywords_page(self, keyword: str, works: List[str]):
        """生成关键词页面"""
        keyword_file = self.base_dir / 'keywords' / f"{keyword}.md"
        content = self._generate_preview_style_page('keywords', keyword, works)

        with open(keyword_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"已生成关键词页面: {keyword_file}")

    def _generate_rank_page(self, rank: str, works: List[str]):
        """生成评分页面"""
        rank_file = self.base_dir / 'ranks' / f"{rank}.md"
        content = self._generate_preview_style_page('ranks', rank, works)

        with open(rank_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"已生成评分页面: {rank_file}")

    def _generate_series_page(self, series: str, works: List[str]):
        """生成系列页面"""
        series_file = self.base_dir / 'series' / f"{series}.md"
        content = self._generate_preview_style_page('series', series, works)

        with open(series_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"已生成系列页面: {series_file}")

    def _generate_year_page(self, year: str, works: List[str]):
        """生成年份页面"""
        year_file = self.base_dir / 'years' / f"{year}.md"
        content = self._generate_preview_style_page('years', year, works)

        with open(year_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"已生成年份页面: {year_file}")

    def _generate_preview_style_page(self, category_type: str, category_value: str, works: List[str]) -> str:
        """生成preview.md样式的分类页面内容"""

        # 根据分类类型设置配置
        type_configs = {
            'actor': {
                'title': f"👰 演员: {category_value}",
                'icon': '👰',
                'filter_field': 'Actor',
                'filter_value': category_value
            },
            'keywords': {
                'title': f"🏷️ 关键词: {category_value}",
                'icon': '🏷️',
                'filter_field': 'Keywords',
                'filter_value': category_value
            },
            'ranks': {
                'title': f"⭐ 评分: {category_value}分",
                'icon': '⭐',
                'filter_field': 'VideoRank',
                'filter_value': category_value
            },
            'series': {
                'title': f"📺 系列: {category_value}",
                'icon': '📺',
                'filter_field': 'Series',
                'filter_value': category_value
            },
            'years': {
                'title': f"📅 年份: {category_value}年",
                'icon': '📅',
                'filter_field': 'Year',
                'filter_value': category_value
            }
        }

        config = type_configs.get(category_type, type_configs['actor'])

        content = f"""---
cssclasses:
  - cards-cols-6
  - cards-cover
  - table-max
  - cards
---

# {config['title']}

```dataviewjs

// === 分类专属页面配置 ===
const CATEGORY_TYPE = "{category_type}";
const CATEGORY_VALUE = "{category_value}";
const ROOT = "jav_store";
const META_DIR = `${{ROOT}}/films`;
const COVER_DIR = `${{ROOT}}/source`;

// 分类目录常量
const ACTOR_DIR = `${{ROOT}}/actor`;
const YEARS_DIR = `${{ROOT}}/years`;
const RANKS_DIR = `${{ROOT}}/ranks`;
const SERIES_DIR = `${{ROOT}}/series`;
const KEYWORDS_DIR = `${{ROOT}}/keywords`;

// === 获取分类页面数据 ===
const allPages = dv.pages(`"${{META_DIR}}"`);
let categoryPages = filterByCategory(allPages).sort(p => p.Code ?? "", "asc");

// 如果过滤结果为空，使用备用过滤逻辑
if (categoryPages.length === 0) {{
  let simpleFiltered = [];
  if (CATEGORY_TYPE === 'keywords') {{
    // 关键词的备用过滤：直接检查Keywords字段
    simpleFiltered = allPages.filter(p => {{
      const keywords = p.Keywords || [];
      const flattenKeywords = (arr) => {{
        let result = [];
        for (const item of arr) {{
          if (Array.isArray(item)) {{
            result = result.concat(flattenKeywords(item));
          }} else if (typeof item === 'string') {{
            result.push(item);
          }}
        }}
        return result;
      }};
      const keywordArray = flattenKeywords(keywords);
      return keywordArray.some(kw => {{
        if (typeof kw === 'object' && kw.path) {{
          return kw.path.split('/').pop() === CATEGORY_VALUE;
        }} else if (typeof kw === 'string') {{
          const cleanKw = kw.replace(/^\\[\\[|\\]\\]$/g, '').split('|').pop().trim();
          return cleanKw === CATEGORY_VALUE;
        }}
        return false;
      }});
    }});
  }} else if (CATEGORY_TYPE === 'actor') {{
    simpleFiltered = allPages.filter(p => {{
      const actor = p.Actor;
      if (Array.isArray(actor)) {{
        const flattenActors = (arr) => {{
          let result = [];
          for (const item of arr) {{
            if (Array.isArray(item)) {{
              result = result.concat(flattenActors(item));
            }} else if (typeof item === 'string' && item.trim()) {{
              result.push(item.trim());
            }}
          }}
          return result;
        }};
        const actorList = flattenActors(actor);
        return actorList.includes(CATEGORY_VALUE);
      }} else if (actor && typeof actor === 'string') {{
        return actor === CATEGORY_VALUE;
      }}
      return false;
    }});
  }} else if (CATEGORY_TYPE === 'years') {{
    // 年份的备用过滤：直接检查Year字段
    simpleFiltered = allPages.filter(p => String(p.Year) === CATEGORY_VALUE);
  }} else {{
    simpleFiltered = allPages.filter(p => String(p[CATEGORY_TYPE.charAt(0).toUpperCase() + CATEGORY_TYPE.slice(1)]) === CATEGORY_VALUE);
  }}
  if (simpleFiltered.length > 0) {{
    categoryPages = simpleFiltered;
  }}
}}

// === 统计信息 ===
const totalCount = categoryPages.length;

// 根据分类类型显示不同的统计信息
let statsText = `**📊 作品总数**: ${{totalCount}} 部`;

// 不再显示重复的分类信息，标题已经包含了完整信息

dv.paragraph(statsText);

// === 通用：把"文件名/相对路径/维基链接/Link对象"解析为 Obsidian 文件对象 ===
function resolveFile(anyPathLike, base){{
  if (!anyPathLike) return null;
  if (typeof anyPathLike === "string"){{
    const s = anyPathLike.trim();
    // [[...]] 维基链接
    const m = s.match(/^\\[\\[([^\\]#|]+)(?:#[^\\]|]+)?(?:\\|([^\\]]+))?\\]\\]$/);
    if (m) return app.metadataCache.getFirstLinkpathDest(m[1], base);
    // 普通相对路径
    return app.vault.getAbstractFileByPath(s);
  }}
  // Dataview 的链接对象
  if (anyPathLike?.path){{
    return app.vault.getAbstractFileByPath(anyPathLike.path)
        ?? app.metadataCache.getFirstLinkpathDest(anyPathLike.path, base);
  }}
  return null;
}}

// === 创建内部链接元素 ===
function makeILink(targetPathOrName, label, sourcePath){{
  const t = String(targetPathOrName ?? "").trim();
  const src = sourcePath ?? dv.current().file.path;
  const dest = app.metadataCache.getFirstLinkpathDest(t, src);
  const a = document.createElement('a');
  a.classList.add('internal-link');
  const href = dest ? dest.path : t;
  a.setAttribute('href', href);
  a.setAttribute('data-href', href);
  a.textContent = label ?? (dest ? dest.basename : t);
  return a;
}}

// === 封面查找：从source目录的番号文件夹中查找封面 ===
function findCoverForPage(p){{
  let v = p.Cover;
  if (!v) return null;

  // 直接按Cover路径解析
  let f = resolveFile(v, p.file.path);
  if (f) return f;

  // 兜底：在source目录的番号文件夹中查找封面
  const code = p.Code;
  if (code) {{
    // 生成可能的目录名称变体
    const getDirectoryVariants = (baseCode) => {{
      const variants = [baseCode];

      // 如果以数字结尾，尝试添加-C后缀
      if (/\\d+$/.test(baseCode)) {{
        variants.push(baseCode + '-C');
      }}

      // 如果已经以-C结尾，也尝试不带-C的版本
      if (baseCode.endsWith('-C')) {{
        variants.push(baseCode.slice(0, -2));
      }}

      return variants;
    }};

    const directoryVariants = getDirectoryVariants(code);

    // 尝试所有可能的目录名称变体
    for (const dirVariant of directoryVariants) {{
      const coverPaths = [
        `${{COVER_DIR}}/${{dirVariant}}/${{dirVariant}}-thumb.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/${{dirVariant}}-poster.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/poster.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/cover.jpg`,
        `${{COVER_DIR}}/${{dirVariant}}/thumb.jpg`
      ];

      for (const coverPath of coverPaths) {{
        const candidate = resolveFile(coverPath, p.file.path);
        if (candidate) return candidate;
      }}
    }}
  }}

  return null;
}}

// === 关键词页面所在文件夹 ===
const KW_DIR = KEYWORDS_DIR;

function kwLinksCell(p){{
  const raw = p.Keywords;
  let arr = [];

  // 统一成数组
  if (Array.isArray(raw)) {{
    arr = raw;
  }} else if (typeof raw === 'string') {{
    arr = raw.split(/[,，;；、\\s]+/);
  }} else {{
    arr = [];
  }}

  // 创建容器元素
  const container = document.createElement('div');
  container.className = 'kw-badges';

  // 逐个创建徽章元素
  arr.forEach(k => {{
    if (!k) return;

    let target, label;
    if (typeof k === 'object' && k.path) {{
      target = k.path;
      label = k.display ?? k.path.split('/').pop();
    }} else {{
      let t = String(k).trim();
      if (!t) return;
      if (/^\\[\\[.*\\]\\]$/.test(t)) {{
        // 已经是 [[...]] 格式
        const m = t.match(/^\\[\\[([^\\]#|]+)(?:#[^\\]|]+)?(?:\\|([^\\]]+))?\\]\\]$/);
        if (m) {{
          target = m[1];
          label = m[2] ?? m[1].split('/').pop();
        }}
      }} else {{
        // 普通字符串，添加目录前缀
        target = KW_DIR ? `${{KW_DIR}}/${{t}}` : t;
        label = t;
      }}
    }}

    // 创建徽章元素
    const badge = document.createElement('span');
    badge.className = 'kw';

    // 创建内部链接元素
    const link = makeILink(target, label, dv.current().file.path);
    badge.appendChild(link);

    container.appendChild(badge);
  }});

  return container;
}}

// === 根据分类类型获取过滤函数 ===
function filterByCategory(pages) {{
  if (CATEGORY_TYPE === 'keywords') {{
    // 关键词过滤：检查Keywords字段中是否包含当前关键词
    return pages.where(p => {{
      const keywords = p.Keywords || [];
      // 处理嵌套数组格式: [[- - keyword1], [- - keyword2]]
      const flattenKeywords = (arr) => {{
        let result = [];
        for (const item of arr) {{
          if (Array.isArray(item)) {{
            result = result.concat(flattenKeywords(item));
          }} else if (typeof item === 'string') {{
            result.push(item);
          }}
        }}
        return result;
      }};
      const keywordArray = flattenKeywords(keywords);
      return keywordArray.some(kw => {{
        if (typeof kw === 'object' && kw.path) {{
          return kw.path.split('/').pop() === CATEGORY_VALUE;
        }} else if (typeof kw === 'string') {{
          const cleanKw = kw.replace(/^\\[\\[|\\]\\]$/g, '').split('|').pop().trim();
          return cleanKw === CATEGORY_VALUE;
        }}
        return false;
      }});
    }});
  }} else {{
    // 其他分类：直接比较字段值
    if (CATEGORY_TYPE === 'actor') {{
      return pages.where(p => {{
        const actor = p.Actor;
        // 处理Actor字段的不同格式：字符串、数组、嵌套数组
        if (Array.isArray(actor)) {{
          // 处理嵌套数组，如 [["上原瑞穂"]]
          const flattenActors = (arr) => {{
            let result = [];
            for (const item of arr) {{
              if (Array.isArray(item)) {{
                result = result.concat(flattenActors(item));
              }} else if (typeof item === 'string' && item.trim()) {{
                result.push(item.trim());
              }}
            }}
            return result;
          }};
          const actorList = flattenActors(actor);
          return actorList.includes(CATEGORY_VALUE);
        }} else if (actor && typeof actor === 'string') {{
          // 如果是字符串，直接比较
          return actor === CATEGORY_VALUE;
        }}
        return false;
      }});
    }} else if (CATEGORY_TYPE === 'ranks') {{
      return pages.where(p => p.VideoRank == CATEGORY_VALUE);
    }} else if (CATEGORY_TYPE === 'series') {{
      return pages.where(p => {{
        const series = p.Series;
        // 处理Series字段的不同格式：字符串、数组、嵌套数组
        if (Array.isArray(series)) {{
          // 处理嵌套数组，如 [["俺だけの尻コス娘"]]
          const flattenSeries = (arr) => {{
            let result = [];
            for (const item of arr) {{
              if (Array.isArray(item)) {{
                result = result.concat(flattenSeries(item));
              }} else if (typeof item === 'string' && item.trim()) {{
                result.push(item.trim());
              }}
            }}
            return result;
          }};
          const seriesList = flattenSeries(series);
          return seriesList.includes(CATEGORY_VALUE);
        }} else if (series && typeof series === 'string') {{
          // 如果是字符串，直接比较
          return series === CATEGORY_VALUE;
        }}
        return false;
      }});
    }} else if (CATEGORY_TYPE === 'years') {{
      return pages.where(p => p.Year === CATEGORY_VALUE);
    }} else {{
      return pages.where(p => p[CATEGORY_TYPE.charAt(0).toUpperCase() + CATEGORY_TYPE.slice(1, -1)] === CATEGORY_VALUE);
    }}
  }}
}}

// === 输出表格 ===
dv.table(
  ["Cover", "CN", "JP", "Code", "Actor", "Year", "Time", "Rank", "Keywords"],
  categoryPages.map(p => {{
    const coverFile = findCoverForPage(p);
    const coverHtml = coverFile
      ? `<img class="myTableImg" src="${{app.vault.adapter.getResourcePath(coverFile.path)}}" loading="lazy">`
      : `<div class="myTableImg no-cover-placeholder" style="
          width: 100px;
          height: 210px;
          border-radius: 8px;
          background: var(--background-secondary);
          border: 2px dashed var(--text-muted);
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
          box-sizing: border-box;
          margin: 0 auto;
        ">
          <div class="no-cover-text" style="
            color: var(--text-muted);
            font-size: 11px;
            font-weight: 500;
            text-align: center;
            line-height: 1.2;
            opacity: 0.8;
            user-select: none;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          ">No Cover</div>
        </div>`;

      // 处理Actor字段显示
    let actorDisplay = "";

    // 辅助函数：处理Actor字段的不同格式
    const getActorList = (actorField) => {{
      if (!actorField) return [];
      if (Array.isArray(actorField)) {{
        // 处理嵌套数组，如 [["上原瑞穂"]]
        const flattenActors = (arr) => {{
          let result = [];
          for (const item of arr) {{
            if (Array.isArray(item)) {{
              result = result.concat(flattenActors(item));
            }} else if (typeof item === 'string' && item.trim()) {{
              result.push(item.trim());
            }}
          }}
          return result;
        }};
        return flattenActors(actorField);
      }} else if (typeof actorField === 'string') {{
        // 处理逗号分隔的字符串
        return actorField.split(',').map(a => a.trim()).filter(Boolean);
      }}
      return [];
    }};

    if (CATEGORY_TYPE === 'actor') {{
      // 如果是演员页面，需要显示该作品的其他演员
      const allActors = getActorList(p.Actor).filter(a => a !== CATEGORY_VALUE);
      if (allActors.length > 0) {{
        actorDisplay = allActors.map(a => `[[${{ACTOR_DIR}}/${{a}}|${{a}}]]`).join(', ');
      }} else {{
        actorDisplay = CATEGORY_VALUE; // 如果没有其他演员，显示当前演员
      }}
    }} else {{
      // 如果不是演员页面，正常显示演员
      const actors = getActorList(p.Actor);
      actorDisplay = actors.map(a => `[[${{ACTOR_DIR}}/${{a}}|${{a}}]]`).join(', ');
    }}

    return [
      coverHtml,
      "🇨🇳" + " " + (p.CN ?? ""),
      "🇯🇵" + " " + (p.JP ?? ""),
      "🪪 " + "[[" + (p.Code ?? "") + "]]",
      "👰 " + actorDisplay,
      "📅 " + "[[" + (p.Year ? `${{YEARS_DIR}}/${{p.Year}}` : "") + "|" + (p.Year ?? "") + "]]",
      "🕒 " + (p.Time ?? ""),
      "🌡️ " + "[[" + (p.VideoRank ? `${{RANKS_DIR}}/${{p.VideoRank}}` : "") + "|" + (p.VideoRank ?? "") + "]]",
      kwLinksCell(p),
    ];
  }})
);

```
"""
        return content


if __name__ == "__main__":
    main()