---
cssclasses:
  - cards-cols-6
  - cards-cover
  - table-max
  - cards
---
```dataviewjs

// === 路径常量（适配当前jav_store结构） ===
const ROOT = "jav_store";
const META_DIR = `${ROOT}/films`;
const COVER_DIR = `${ROOT}/source`;

// 分类目录常量
const ACTOR_DIR = `${ROOT}/actor`;
const YEARS_DIR = `${ROOT}/years`;
const RANKS_DIR = `${ROOT}/ranks`;
const SERIES_DIR = `${ROOT}/series`;
const KEYWORDS_DIR = `${ROOT}/keywords`;

// === 通用：把"文件名/相对路径/维基链接/Link对象"解析为 Obsidian 文件对象 ===
function resolveFile(anyPathLike, base){
  if (!anyPathLike) return null;
  if (typeof anyPathLike === "string"){
    const s = anyPathLike.trim();
    // [[...]] 维基链接
    const m = s.match(/^\[\[([^\]#|]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]$/);
    if (m) return app.metadataCache.getFirstLinkpathDest(m[1], base);
    // 普通相对路径
    return app.vault.getAbstractFileByPath(s);
  }
  // Dataview 的链接对象
  if (anyPathLike?.path){
    return app.vault.getAbstractFileByPath(anyPathLike.path)
        ?? app.metadataCache.getFirstLinkpathDest(anyPathLike.path, base);
  }
  return null;
}

// === 创建内部链接元素 ===
function makeILink(targetPathOrName, label, sourcePath){
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
}

// === 封面查找：从source目录的番号文件夹中查找封面 ===
function findCoverForPage(p){
  let v = p.Cover;
  if (!v) return null;

  // 直接按Cover路径解析
  let f = resolveFile(v, p.file.path);
  if (f) return f;

  // 兜底：在source目录的番号文件夹中查找封面
  const code = p.Code;
  if (code) {
    const coverPaths = [
      `${COVER_DIR}/${code}/${code}-thumb.jpg`,
      `${COVER_DIR}/${code}/${code}-poster.jpg`,
      `${COVER_DIR}/${code}/poster.jpg`,
      `${COVER_DIR}/${code}/cover.jpg`,
      `${COVER_DIR}/${code}/thumb.jpg`
    ];

    for (const coverPath of coverPaths) {
      const candidate = resolveFile(coverPath, p.file.path);
      if (candidate) return candidate;
    }
  }

  return null;
}


// === 获取所有页面数据 ===
const pagesAll = dv.pages(`"${META_DIR}"`).sort(p => p.Code ?? "", "asc");

// 关键词页面所在文件夹
const KW_DIR = KEYWORDS_DIR;

function kwLinksCell(p){
  const raw = p.Keywords;
  let arr = [];

  // 统一成数组
  if (Array.isArray(raw)) {
    arr = raw;
  } else if (typeof raw === 'string') {
    arr = raw.split(/[,，;；、\s]+/);
  } else {
    arr = [];
  }

  // 创建容器元素
  const container = document.createElement('div');
  container.className = 'kw-badges';

  // 逐个创建徽章元素
  arr.forEach(k => {
    if (!k) return;

    let target, label;
    if (typeof k === 'object' && k.path) {
      target = k.path;
      label = k.display ?? k.path.split('/').pop();
    } else {
      let t = String(k).trim();
      if (!t) return;
      if (/^\[\[.*\]\]$/.test(t)) {
        // 已经是 [[...]] 格式
        const m = t.match(/^\[\[([^\]#|]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]$/);
        if (m) {
          target = m[1];
          label = m[2] ?? m[1].split('/').pop();
        }
      } else {
        // 普通字符串，添加目录前缀
        target = KW_DIR ? `${KW_DIR}/${t}` : t;
        label = t;
      }
    }

    // 创建徽章元素
    const badge = document.createElement('span');
    badge.className = 'kw';

    // 创建内部链接元素
    const link = makeILink(target, label, dv.current().file.path);
    badge.appendChild(link);

    container.appendChild(badge);
  });

  return container;
}

// === 输出表格 ===
dv.table(
  ["Cover", "CN", "JP", "Code", "Actor", "Year", "Time", "Rank", "Keywords"],
  pagesAll.map(p => {
    const coverFile = findCoverForPage(p);
    const coverHtml = coverFile
      ? `<img class="myTableImg" src="${app.vault.adapter.getResourcePath(coverFile.path)}" loading="lazy">`
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
      "👰 " + "[[" + (p.Actor ? `${ACTOR_DIR}/${p.Actor}` : "") + "|" + (p.Actor ?? "") + "]]",
      "📅 " + "[[" + (p.Year ? `${YEARS_DIR}/${p.Year}` : "") + "|" + (p.Year ?? "") + "]]",
      "🕒 " + (p.Time ?? ""),
      "🌡️ " + "[[" + (p.VideoRank ? `${RANKS_DIR}/${p.VideoRank}` : "") + "|" + (p.VideoRank ?? "") + "]]",
      kwLinksCell(p),
    ];
  })
);

// === 统计信息 ===
const totalCount = pagesAll.length;
const actorCounts = {};
pagesAll.forEach(p => {
  const actor = p.Actor;
  if (actor) {
    actorCounts[actor] = (actorCounts[actor] || 0) + 1;
  }
});

const topActors = Object.entries(actorCounts)
  .sort(([,a], [,b]) => b - a)
  .slice(0, 5)
  .map(([actor, count]) => `${actor} (${count})`)
  .join(", ");

dv.paragraph(`**总计**: ${totalCount} 部作品`);
dv.paragraph(`**演员排行**: ${topActors}`);
```