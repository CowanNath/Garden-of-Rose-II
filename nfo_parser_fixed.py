import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
import logging
import html
import unicodedata
import re
import tempfile
import os

class FixedNFOParser:
    """修复版NFO文件解析器"""

    def __init__(self, config):
        self.config = config
        self.defaults = config.get('nfo_parsing.defaults', {
            'rating': 0.0,
            'studio': '未知',
            'director': '未知',
            'plot': '暂无该部分信息'
        })

    def parse_nfo(self, nfo_path: str) -> dict:
        """解析NFO文件，完全重写版本"""
        logging.info(f"开始解析NFO文件: {nfo_path}")

        # 初始化数据结构
        data = {
            'title': '',
            'actors': [],
            'release_date': '',
            'rating': self.defaults.get('rating', 0.0),
            'plot': self.defaults.get('plot', '暂无该部分信息'),
            'genre': [],  # 确保初始化
            'studio': self.defaults.get('studio', '未知'),
            'director': self.defaults.get('director', '未知'),
            'maker': self.defaults.get('maker', '未知'),
            'publisher': self.defaults.get('publisher', '未知'),
            'series': ''
        }

        # 尝试多种解析方法
        parsers = [
            self._parse_standard_xml,
            self._parse_with_recovery,
            self._parse_line_by_line,
            self._parse_with_minidom
        ]

        for i, parser in enumerate(parsers, 1):
            try:
                logging.debug(f"尝试解析方法 {i}: {nfo_path}")
                result = parser(nfo_path, data)
                if result and self._has_meaningful_data(result):
                    logging.info(f"使用方法 {i} 成功解析: {nfo_path}")
                    return result
            except Exception as e:
                logging.warning(f"解析方法 {i} 失败: {nfo_path} - {e}")
                continue

        logging.warning(f"所有解析方法都失败: {nfo_path}")
        return data

    def _has_meaningful_data(self, data: dict) -> bool:
        """检查是否有有意义的数据"""
        return any([
            data.get('title', '').strip(),
            data.get('studio', '').strip() != '未知',
            data.get('director', '').strip() != '未知',
            data.get('plot', '').strip() != self.defaults.get('plot', ''),
            data.get('rating', 0) > 0,
            len(data.get('actors', [])) > 0,
            len(data.get('genre', [])) > 0,
            data.get('release_date', '').strip()
        ])

    def _parse_standard_xml(self, nfo_path: str, data: dict) -> dict:
        """标准XML解析"""
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        return self._extract_data_safe(root, data)

    def _parse_with_recovery(self, nfo_path: str, data: dict) -> dict:
        """带恢复的XML解析"""
        with open(nfo_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # 修复常见的XML问题
        content = self._fix_xml_issues(content)

        # 使用临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nfo', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            tree = ET.parse(temp_file_path)
            root = tree.getroot()
            result = self._extract_data_safe(root, data)
            logging.info(f"修复解析成功: {nfo_path}")
            return result
        finally:
            os.unlink(temp_file_path)

    def _parse_line_by_line(self, nfo_path: str, data: dict) -> dict:
        """逐行解析NFO文件"""
        with open(nfo_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # 使用正则表达式提取数据
        data['title'] = self._extract_field(content, r'<title[^>]*>(.*?)</title>')
        data['studio'] = self._extract_field(content, r'<studio[^>]*>(.*?)</studio>')
        data['director'] = self._extract_field(content, r'<director[^>]*>(.*?)</director>')
        data['plot'] = self._extract_field(content, r'<plot[^>]*>(.*?)</plot>')
        data['release_date'] = self._extract_field(content, r'<releasedate[^>]*>(.*?)</releasedate>')
        data['series'] = self._extract_field(content, r'<series[^>]*>(.*?)</series>')
        data['runtime'] = self._extract_field(content, r'<runtime[^>]*>(.*?)</runtime>')

        # 提取评分
        rating_text = self._extract_field(content, r'<rating[^>]*>(.*?)</rating>')
        if rating_text:
            try:
                data['rating'] = float(rating_text)
            except ValueError:
                pass

        # 提取类型
        genre_matches = re.findall(r'<genre[^>]*>(.*?)</genre>', content, re.IGNORECASE)
        data['genre'] = [self._clean_text(g) for g in genre_matches if g.strip()]

        # 提取演员
        actor_matches = re.findall(r'<actor[^>]*>.*?<name[^>]*>(.*?)</name>.*?</actor>', content, re.DOTALL)
        data['actors'] = [self._clean_text(a) for a in actor_matches if a.strip()]

        return data

    def _parse_with_minidom(self, nfo_path: str, data: dict) -> dict:
        """使用minidom解析（备用方案）"""
        try:
            from xml.dom import minidom
            doc = minidom.parse(nfo_path)

            # 提取数据
            for elem in doc.getElementsByTagName('title'):
                if elem.firstChild:
                    data['title'] = elem.firstChild.nodeValue
                    break

            for elem in doc.getElementsByTagName('studio'):
                if elem.firstChild:
                    data['studio'] = elem.firstChild.nodeValue
                    break

            for elem in doc.getElementsByTagName('series'):
                if elem.firstChild:
                    data['series'] = elem.firstChild.nodeValue
                    break

            # 其他字段类似...
            return data

        except ImportError:
            raise Exception("minidom不可用")
        except Exception as e:
            raise Exception(f"minidom解析失败: {e}")

    def _extract_field(self, content: str, pattern: str) -> str:
        """提取单个字段"""
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return self._clean_text(match.group(1))
        return ''

    def _extract_data_safe(self, root, data: dict) -> dict:
        """安全的数据提取"""
        try:
            # 提取基本信息
            fields = {
                'title': 'title',
                'originaltitle': 'originaltitle',
                'rating': 'rating',
                'studio': 'studio',
                'director': 'director',
                'maker': 'maker',
                'publisher': 'publisher',
                'plot': 'plot',
                'series': 'series',
                'runtime': 'runtime'
            }

            for field_name, tag_name in fields.items():
                elem = root.find(tag_name)
                if elem is not None and elem.text:
                    value = self._clean_text(elem.text)
                    if value:
                        if field_name == 'rating':
                            try:
                                data[field_name] = float(value)
                            except ValueError:
                                pass
                        else:
                            data[field_name] = value

            # 提取列表字段
            data['genre'] = []
            for genre_elem in root.findall('genre'):
                if genre_elem.text:
                    genre = self._clean_text(genre_elem.text)
                    if genre:
                        data['genre'].append(genre)

            data['actors'] = []
            for actor_elem in root.findall('actor'):
                name_elem = actor_elem.find('name')
                if name_elem is not None and name_elem.text:
                    actor = self._clean_text(name_elem.text)
                    if actor:
                        data['actors'].append(actor)

            # 提取日期
            for date_field in ['releasedate', 'premiered', 'release']:
                elem = root.find(date_field)
                if elem is not None and elem.text:
                    data['release_date'] = self._clean_text(elem.text)
                    break

            return data

        except Exception as e:
            logging.error(f"安全数据提取失败: {e}")
            return data

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ''

        try:
            # HTML实体解码
            text = html.unescape(text)

            # 移除控制字符
            text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C')

            # 清理空白字符
            text = re.sub(r'\s+', ' ', text)

            return text.strip()
        except Exception:
            return text.strip()

    def _fix_xml_issues(self, content: str) -> str:
        """修复XML问题"""
        # 移除无效字符
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', content)

        # 修复常见的XML问题
        content = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', content)

        return content