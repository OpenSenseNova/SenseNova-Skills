export interface PrepareCitationsInput {
    report_path: string;
    sub_report_paths: string[];
}
export interface PrepareCitationsResult {
    success: boolean;
    report_path?: string;
    citations_path?: string;
    total_citations?: number;
    sub_reports_scanned?: string[];
    sub_reports_failed?: {
        path: string;
        error: string;
    }[];
    error?: string;
}
export declare function prepareReportCitationsTool(): {
    name: string;
    label: string;
    description: string;
    parameters: {
        type: "object";
        additionalProperties: boolean;
        required: string[];
        properties: {
            report_path: {
                type: string;
                description: string;
            };
            sub_report_paths: {
                type: string;
                items: {
                    type: string;
                };
                description: string;
            };
        };
    };
    execute(_toolCallId: string, params: PrepareCitationsInput): Promise<{
        content: {
            type: "text";
            text: string;
        }[];
        details: PrepareCitationsResult;
    } | {
        content: {
            type: "text";
            text: string;
        }[];
        details: {
            error: boolean;
            message: string;
        };
    }>;
};
