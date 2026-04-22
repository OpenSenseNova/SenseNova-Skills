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
function normalizeText(raw) {
    return raw.trim().replace(/\s+/g, " ");
}
function parseFootnoteDef(content) {
    const link = MD_LINK_RE.exec(content);
    if (link)
        return { title: link[1].trim(), url: link[2].trim() };
    const url = BARE_URL_RE.exec(content);
    if (url) {
        const cleanUrl = url[0].replace(/[),.;]+$/g, "");
        const title = content
            .slice(0, url.index)
            .trim()
            .replace(/[-,:;]+$/g, "")
            .trim();
        return { title: title || cleanUrl, url: cleanUrl };
    }
    return { title: content.trim(), url: "" };
}
export class CitationManager {
    definitions = new Map();
    pool = new Map();
    collectDefinitions(text, source = { kind: "sub", order: 0 }) {
        FOOTNOTE_DEF_RE.lastIndex = 0;
        let m;
        while ((m = FOOTNOTE_DEF_RE.exec(text)) !== null) {
            const key = m[1];
            const { title, url } = parseFootnoteDef(m[2]);
            const identity = url ? `url:${normalizeUrl(url)}` : `text:${normalizeText(title)}`;
            this.definitions.set(key, { title, url, identity });
            const existing = this.pool.get(identity);
            if (!existing) {
                this.pool.set(identity, {
                    key,
                    url,
                    title,
                    index: 0,
                    aliasKeys: [key],
                    identity,
                    sourceKind: source.kind,
                    sourceOrder: source.order,
                });
                continue;
            }
            if (!existing.aliasKeys.includes(key)) {
                existing.aliasKeys.push(key);
            }
            const shouldReplace = (source.kind === "final" && existing.sourceKind !== "final") ||
                (source.kind === existing.sourceKind && source.order >= existing.sourceOrder);
            if (shouldReplace) {
                existing.key = key;
                existing.url = url;
                existing.title = title;
                existing.sourceKind = source.kind;
                existing.sourceOrder = source.order;
            }
        }
    }
    processReport(reportText) {
        const keyToIndex = new Map();
        const identityToIndex = new Map();
        const ordered = [];
        let counter = 0;
        const resolveCitation = (key) => {
            const def = this.definitions.get(key);
            if (def) {
                const citation = this.pool.get(def.identity);
                if (citation) {
                    return citation;
                }
            }
            const identity = `missing:${key}`;
            const existing = this.pool.get(identity);
            if (existing) {
                return existing;
            }
            const fallback = {
                key,
                url: "",
                title: def?.title ?? key,
                index: 0,
                aliasKeys: [key],
                identity,
                sourceKind: "final",
                sourceOrder: Number.MAX_SAFE_INTEGER,
            };
            this.pool.set(identity, fallback);
            return fallback;
        };
        const assignCitation = (citation) => {
            const existing = identityToIndex.get(citation.identity);
            if (existing) {
                return existing;
            }
            counter += 1;
            citation.index = counter;
            identityToIndex.set(citation.identity, counter);
            ordered.push(citation);
            return counter;
        };
        FOOTNOTE_REF_RE.lastIndex = 0;
        let m;
        while ((m = FOOTNOTE_REF_RE.exec(reportText)) !== null) {
            const key = m[1];
            const citation = resolveCitation(key);
            const idx = assignCitation(citation);
            if (!keyToIndex.has(key)) {
                keyToIndex.set(key, idx);
            }
            for (const aliasKey of citation.aliasKeys) {
                if (!keyToIndex.has(aliasKey)) {
                    keyToIndex.set(aliasKey, idx);
                }
            }
        }
        for (const citation of this.pool.values()) {
            const idx = assignCitation(citation);
            for (const aliasKey of citation.aliasKeys) {
                if (!keyToIndex.has(aliasKey)) {
                    keyToIndex.set(aliasKey, idx);
                }
            }
        }
        let processed = reportText.replace(FOOTNOTE_REF_RE, (_, k) => {
            const idx = keyToIndex.get(k);
            return idx ? `[${idx}]` : `[^${k}]`;
        });
        processed = processed.replace(FOOTNOTE_DEF_RE, "").replace(/\n{3,}/g, "\n\n").trim();
        const refLines = ordered.map((c) => c.url ? `[${c.index}] [${c.title}](${c.url})` : `[${c.index}] ${c.title}`);
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