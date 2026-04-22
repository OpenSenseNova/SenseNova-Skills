export interface Citation {
    key: string;
    url: string;
    title: string;
    index: number;
    aliasKeys: string[];
    identity: string;
    sourceKind: "sub" | "final";
    sourceOrder: number;
}
export declare class CitationManager {
    private definitions;
    private pool;
    collectDefinitions(text: string, source?: {
        kind: "sub" | "final";
        order: number;
    }): void;
    processReport(reportText: string): {
        processed: string;
        references: string;
    };
    exportJson(): {
        total_citations: number;
        citations: Array<Pick<Citation, "index" | "key" | "url" | "title" | "aliasKeys">>;
    };
}
