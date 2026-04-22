// Volcengine (火山方舟) Doubao Seedream image generation provider.
// 把现有 skills/generate-image/scripts/generate_image.py 的逻辑搬到
// OpenClaw plugin runtime，让所有 agent 通过内置 image_generate 工具直接调用。
//
// 启用：在启动 openclaw 的 shell 环境中设置 ARK_API_KEY（或 VOLCANO_ENGINE_API_KEY）。
// 可选：ARK_BASE_URL 覆盖默认端点。

import type {
  GeneratedImageAsset,
  ImageGenerationProvider,
  ImageGenerationResult,
} from "openclaw/plugin-sdk/image-generation";
import { readVolcengineEnv } from "./volcengine_env.js";

const PROVIDER_ID = "volcengine-image";
const DEFAULT_MODEL = "doubao-seedream-5-0-260128";
const SUPPORTED_MODELS = [DEFAULT_MODEL];
const SUPPORTED_SIZES = ["1024x1024", "2K", "4K"];
const DEFAULT_TIMEOUT_MS = 120_000;

type SeedreamImage = {
  b64_json?: string;
  url?: string;
  revised_prompt?: string;
};

type SeedreamResponse = {
  data?: SeedreamImage[];
  error?: { message?: string };
};

function detectMimeType(buf: Buffer): string {
  if (buf.length >= 4 && buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47) {
    return "image/png";
  }
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) {
    return "image/jpeg";
  }
  if (
    buf.length >= 12 &&
    buf.slice(0, 4).toString("ascii") === "RIFF" &&
    buf.slice(8, 12).toString("ascii") === "WEBP"
  ) {
    return "image/webp";
  }
  return "image/png";
}

function extensionForMime(mimeType: string): string {
  if (mimeType === "image/jpeg") return "jpg";
  if (mimeType === "image/webp") return "webp";
  return "png";
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function downloadImage(url: string, timeoutMs: number): Promise<Buffer> {
  const resp = await fetchWithTimeout(url, {}, timeoutMs);
  if (!resp.ok) {
    throw new Error(`Volcengine 图片下载失败 (${resp.status})`);
  }
  const arr = await resp.arrayBuffer();
  return Buffer.from(arr);
}

export function buildVolcengineImageProvider(): ImageGenerationProvider {
  return {
    id: PROVIDER_ID,
    aliases: ["doubao", "doubao-image", "seedream"],
    label: "Volcengine Doubao Seedream",
    defaultModel: DEFAULT_MODEL,
    models: SUPPORTED_MODELS,
    capabilities: {
      generate: {
        maxCount: 1,
        supportsSize: true,
        supportsAspectRatio: false,
        supportsResolution: true,
      },
      edit: { enabled: false },
      geometry: {
        sizes: [...SUPPORTED_SIZES],
        resolutions: ["1K", "2K", "4K"],
      },
    },
    isConfigured: () => readVolcengineEnv().apiKey !== undefined,
    async generateImage(req): Promise<ImageGenerationResult> {
      const { apiKey, baseUrl } = readVolcengineEnv();
      if (!apiKey) {
        throw new Error(
          "Volcengine 图像生成缺少 API Key：请设置环境变量 ARK_API_KEY（或 VOLCANO_ENGINE_API_KEY）",
        );
      }
      if ((req.inputImages?.length ?? 0) > 0) {
        throw new Error("Volcengine Seedream 暂不支持图像编辑（inputImages）");
      }
      const model = req.model?.trim() || DEFAULT_MODEL;
      const size = req.size?.trim() || req.resolution || "2K";
      const timeoutMs = req.timeoutMs ?? DEFAULT_TIMEOUT_MS;

      const body = {
        model,
        prompt: req.prompt,
        n: req.count ?? 1,
        size,
        response_format: "b64_json",
        watermark: false,
      };

      const resp = await fetchWithTimeout(
        `${baseUrl}/images/generations`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${apiKey}`,
          },
          body: JSON.stringify(body),
        },
        timeoutMs,
      );

      if (!resp.ok) {
        const errText = await resp.text().catch(() => "");
        throw new Error(`Volcengine 图像生成失败 (${resp.status}): ${errText || resp.statusText}`);
      }

      const payload = (await resp.json()) as SeedreamResponse;
      const data = payload.data ?? [];
      if (data.length === 0) {
        const apiMsg = payload.error?.message;
        throw new Error(apiMsg ? `Volcengine 返回错误: ${apiMsg}` : "Volcengine 返回空结果");
      }

      const images: GeneratedImageAsset[] = [];
      for (let i = 0; i < data.length; i += 1) {
        const entry = data[i]!;
        let buf: Buffer | null = null;
        if (entry.b64_json) {
          buf = Buffer.from(entry.b64_json, "base64");
        } else if (entry.url) {
          buf = await downloadImage(entry.url, timeoutMs);
        }
        if (!buf) continue;
        const mimeType = detectMimeType(buf);
        images.push({
          buffer: buf,
          mimeType,
          fileName: `seedream-${i + 1}.${extensionForMime(mimeType)}`,
          revisedPrompt: entry.revised_prompt,
        });
      }

      if (images.length === 0) {
        throw new Error("Volcengine 返回的图片数据为空（b64_json 与 url 均缺失）");
      }

      return {
        images,
        model,
        metadata: { provider: PROVIDER_ID, size },
      };
    },
  };
}
