export interface Citation {
    key: string;
    url: string;
    title: string;
    index: number;
    aliasKeys: string[];
}
export declare class CitationManager {
    private definitions;
    private pool;
    private keyToNormUrl;
    collectDefinitions(text: string): void;
    processReport(reportText: string): {
        processed: string;
        references: string;
    };
    exportJson(): {
        total_citations: number;
        citations: Array<Pick<Citation, "index" | "key" | "url" | "title" | "aliasKeys">>;
    };
}
