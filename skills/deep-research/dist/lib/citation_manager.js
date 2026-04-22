// 引用管理器：解析 [^key] 脚注，按 URL 去重，分配 [N] 编号
// TS 端口自 sensenova_claw/capabilities/deep_research/citation_manager.py
function normalizeUrl(raw) {
    try {
        const u = new URL(raw.trim());
        const path = u.pathname.replace(/\/+$/, "") || "";
        return `${u.protocol.toLowerCase()}//${u.host.toLowerCase()}${path}${u.search}`;
    }
    catch {
        return raw.trim();
    }
}
// 正文引用：[^key]，后面不接冒号
const FOOTNOTE_REF_RE = /\[\^([\w-]+)\](?!:)/g;
// 脚注定义：行首 [^key]: ...
const FOOTNOTE_DEF_RE = /^\[\^([\w-]+)\]:\s*(.+)$/gm;
// 脚注定义内部的 Markdown 链接
const MD_LINK_RE = /\[([^\]]+)\]\(([^)]+)\)/;
const BARE_URL_RE = /https?:\/\/\S+/;
function parseFootnoteDef(content) {
    const link = MD_LINK_RE.exec(content);
    if (link)
        return { title: link[1].trim(), url: link[2].trim() };
    const url = BARE_URL_RE.exec(content);
    if (url) {
        const title = content.slice(0, url.index).trim().replace(/-$/, "").trim();
        return { title: title || url[0], url: url[0] };
    }
    return { title: content.trim(), url: "" };
}
export class CitationManager {
    definitions = new Map();
    pool = new Map();
    keyToNormUrl = new Map();
    collectDefinitions(text) {
        FOOTNOTE_DEF_RE.lastIndex = 0;
        let m;
        while ((m = FOOTNOTE_DEF_RE.exec(text)) !== null) {
            const key = m[1];
            const { title, url } = parseFootnoteDef(m[2]);
            this.definitions.set(key, { title, url });
            if (!url)
                continue;
            const norm = normalizeUrl(url);
            this.keyToNormUrl.set(key, norm);
            const existing = this.pool.get(norm);
            if (!existing) {
                this.pool.set(norm, { key, url, title, index: 0, aliasKeys: [key] });
            }
            else if (!existing.aliasKeys.includes(key)) {
                existing.aliasKeys.push(key);
            }
        }
    }
    processReport(reportText) {
        const keyToIndex = new Map();
        const ordered = [];
        let counter = 0;
        FOOTNOTE_REF_RE.lastIndex = 0;
        let m;
        while ((m = FOOTNOTE_REF_RE.exec(reportText)) !== null) {
            const key = m[1];
            const norm = this.keyToNormUrl.get(key);
            if (norm && this.pool.has(norm)) {
                const citation = this.pool.get(norm);
                const primaryKey = citation.key;
                if (!keyToIndex.has(primaryKey)) {
                    counter += 1;
                    citation.index = counter;
                    keyToIndex.set(primaryKey, counter);
                    ordered.push(citation);
                }
                if (!keyToIndex.has(key)) {
                    keyToIndex.set(key, keyToIndex.get(primaryKey));
                }
            }
            else if (!keyToIndex.has(key)) {
                counter += 1;
                const def = this.definitions.get(key);
                const fallback = {
                    key,
                    url: "",
                    title: def?.title ?? key,
                    index: counter,
                    aliasKeys: [key],
                };
                keyToIndex.set(key, counter);
                ordered.push(fallback);
            }
        }
        let processed = reportText.replace(FOOTNOTE_REF_RE, (_, k) => {
            const idx = keyToIndex.get(k);
            return idx ? `[${idx}]` : `[^${k}]`;
        });
        processed = processed.replace(FOOTNOTE_DEF_RE, "").replace(/\n{3,}/g, "\n\n").trim();
        const refLines = ordered.map((c) => c.url ? `${c.index}. [${c.title}](${c.url})` : `${c.index}. ${c.title}`);
        return { processed, references: refLines.join("\n") };
    }
    exportJson() {
        const items = [...this.pool.values()].filter((c) => c.index > 0).sort((a, b) => a.index - b.index);
        return {
            total_citations: items.length,
            citations: items.map((c) => ({
                index: c.index,
                key: c.key,
                url: c.url,
                title: c.title,
                aliasKeys: c.aliasKeys,
            })),
        };
    }
}
//# sourceMappingURL=citation_manager.js.map