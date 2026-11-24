'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Check, Download, ImagePlus, Layers, Loader2, Sparkles, Upload, Wand2, X } from 'lucide-react';
import type { CuratedShowcaseAsset } from '@/types/aethervault';

interface NanoBananaFusionModalProps {
  isOpen: boolean;
  selectedAssets: CuratedShowcaseAsset[];
  onRemoveAsset: (assetId: string) => void;
  onClose: () => void;
}

interface FusionResult {
  model: string;
  image_url: string;
  aspect_ratio: string;
  reference_ids: string[];
  reference_titles: string[];
  compiled_tokens: string[];
  compiled_prompt: string;
  latency_ms: number;
}

export const NanoBananaFusionModal: React.FC<NanoBananaFusionModalProps> = ({
  isOpen,
  selectedAssets,
  onRemoveAsset,
  onClose,
}) => {
  const [prompt, setPrompt] = useState('');
  const [aspectRatio, setAspectRatio] = useState<'4:3' | '1:1' | '3:4' | '16:9'>('4:3');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FusionResult | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/atlas/fuse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_ids: selectedAssets.map((a) => a.asset_id),
          prompt: prompt.trim(),
          aspect_ratio: aspectRatio,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || `融合出图失败 (HTTP ${res.status})`);
      }
      setResult(data as FusionResult);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : '请确认本地 FastAPI (127.0.0.1:8780) 已启动并配置了 GEMINI_API_KEY。'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="fusion-modal-title"
      onClick={onClose}
      className="fixed inset-0 z-[65] !mt-0 bg-black/70 backdrop-blur-[2px] flex items-center justify-center p-3 sm:p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto p-5 sm:p-6 space-y-5"
      >
        <div className="flex items-start justify-between gap-3 pb-3 border-b border-border">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
              <Wand2 className="w-3.5 h-3.5" />
              <span>Gemini Nano Banana 2.1 · 受控 RAG 跨界融合出图</span>
            </div>
            <h2 id="fusion-modal-title" className="font-display text-lg font-extrabold text-foreground">
              多图美学基因融合工作台
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭融合工作台"
            className="w-8 h-8 rounded-md border border-border hover:border-primary/60 flex items-center justify-center text-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Selected Reference Slots (up to 3) */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-foreground">已选参考图槽位（最多 3 张，自动注入受控 RAG Tokens）</span>
            <span className="mono text-muted-foreground">{selectedAssets.length} / 3</span>
          </div>
          {selectedAssets.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-secondary/30 p-4 text-xs text-muted-foreground text-center">
              暂未勾选参考图——你可以直接输入文字生成，或关闭弹窗在画廊 / 2D 语义画布中点选或框选 1–3 张参考图。
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {selectedAssets.map((a) => (
                <div key={a.asset_id} className="rounded-lg border border-border bg-secondary/35 p-2 flex items-center gap-2.5">
                  <img
                    src={a.image_url}
                    alt={a.title}
                    className="w-14 h-11 rounded object-cover border border-border shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold text-foreground truncate">{a.title}</div>
                    <div className="text-[11px] text-primary truncate">
                      {a.archetype_label} · {a.aesthetic_style_zh}
                    </div>
                  </div>
                  <button
                    type="button"
                    aria-label={`移除参考图 ${a.title}`}
                    onClick={() => onRemoveAsset(a.asset_id)}
                    className="p-1 text-muted-foreground hover:text-foreground shrink-0"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Prompt & Aspect Ratio Controls */}
        <div className="space-y-2.5">
          <label htmlFor="fusion-prompt" className="text-xs font-semibold text-foreground block">
            创作融合指令（可选，留空则自动正交融合所选参考图的构筑、材质与光影）
          </label>
          <textarea
            id="fusion-prompt"
            rows={2}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="例：将图1的穿孔铝板高技立面与图2的侘寂暖木茶室氛围融合，设计一座滨水社区咖啡亭，柔和晨光..."
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
          />

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-muted-foreground">画幅比例：</span>
              {(['4:3', '1:1', '3:4', '16:9'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setAspectRatio(r)}
                  className={`h-7 px-2.5 rounded-md border mono text-xs transition-colors ${
                    aspectRatio === r
                      ? 'border-primary bg-primary text-primary-foreground font-semibold'
                      : 'border-border bg-card text-foreground hover:border-primary/60'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>

            <button
              type="button"
              disabled={loading || (selectedAssets.length === 0 && !prompt.trim())}
              onClick={handleGenerate}
              className="min-h-[38px] px-5 rounded-md bg-primary hover:bg-primary/90 disabled:opacity-50 text-primary-foreground text-xs font-semibold inline-flex items-center gap-1.5 transition-colors"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              <span>{loading ? 'Nano Banana 2.1 生成中...' : '生成跨界融合概念图'}</span>
            </button>
          </div>
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/50 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive">
            {error}
          </div>
        )}

        {/* Output Preview */}
        {result && (
          <div className="rounded-xl border border-border bg-secondary/35 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="font-bold text-foreground inline-flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-primary" />
                <span>生成结果 · {result.model} ({(result.latency_ms / 1000).toFixed(1)}s)</span>
              </span>
              <a
                href={result.image_url}
                download
                className="h-7 px-2.5 rounded-md border border-border hover:border-primary/60 bg-card text-xs font-medium text-foreground inline-flex items-center gap-1"
              >
                <Download className="w-3 h-3" />
                <span>下载原图 JPG</span>
              </a>
            </div>

            <div className="rounded-lg overflow-hidden border border-border bg-background flex items-center justify-center">
              <img
                src={result.image_url}
                alt="Nano Banana 2.1 跨界美学融合生成图"
                className="max-h-[420px] w-auto max-w-full object-contain"
              />
            </div>

            {result.compiled_tokens.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {result.compiled_tokens.map((tok) => (
                  <span key={tok} className="mono rounded px-1.5 py-0.5 text-[10px] border border-border bg-card text-muted-foreground">
                    {tok}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

interface DropInIngestModalProps {
  isOpen: boolean;
  onIngested: (newAssets: CuratedShowcaseAsset[]) => void;
  onClose: () => void;
}

interface IngestItemReport {
  filename: string;
  status: string;
  asset_id?: string;
  title?: string;
  archetype_label?: string;
  aesthetic_style_zh?: string;
  native_style_primary?: string;
  reason?: string;
}

export const DropInIngestModal: React.FC<DropInIngestModalProps> = ({
  isOpen,
  onIngested,
  onClose,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [sourceLabel, setSourceLabel] = useState('Drop-In 网页导入');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<{
    added_count: number;
    skipped_count: number;
    total_assets: number;
    latency_ms: number;
    items: IngestItemReport[];
  } | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setError(null);
    setReport(null);
    try {
      const form = new FormData();
      files.forEach((f) => form.append('files', f));
      form.append('source_label', sourceLabel.trim() || 'Drop-In 网页导入');
      const res = await fetch('/api/atlas/ingest', {
        method: 'POST',
        body: form,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || `入库失败 (HTTP ${res.status})`);
      }
      setReport(data);
      if (Array.isArray(data.added_assets) && data.added_assets.length > 0) {
        onIngested(data.added_assets as CuratedShowcaseAsset[]);
      }
      setFiles([]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : '请确认本地 FastAPI (127.0.0.1:8780) 已启动并配置了 GEMINI_API_KEY。'
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ingest-modal-title"
      onClick={onClose}
      className="fixed inset-0 z-[65] !mt-0 bg-black/70 backdrop-blur-[2px] flex items-center justify-center p-3 sm:p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-2xl max-h-[88vh] overflow-y-auto p-5 sm:p-6 space-y-5"
      >
        <div className="flex items-start justify-between gap-3 pb-3 border-b border-border">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
              <ImagePlus className="w-3.5 h-3.5" />
              <span>Drop-In 一键增量入库（pHash 去重 → Gemini 4 Hydrogen → Embedding 2）</span>
            </div>
            <h2 id="ingest-modal-title" className="font-display text-lg font-extrabold text-foreground">
              导入新参考图至个人审美图谱
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭增量导入弹窗"
            className="w-8 h-8 rounded-md border border-border hover:border-primary/60 flex items-center justify-center text-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const dropped = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('image/'));
            if (dropped.length > 0) setFiles((prev) => [...prev, ...dropped].slice(0, 12));
          }}
          className="rounded-xl border-2 border-dashed border-border hover:border-primary/60 bg-secondary/30 p-6 text-center space-y-3 transition-colors"
        >
          <Upload className="w-7 h-7 mx-auto text-primary" />
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">拖拽图片到此处，或点击选择文件（单次最多 12 张）</div>
            <p className="text-xs text-muted-foreground">
              自动去重、归入 8 大域与模型原生风格词、生成 4 键 RAG 标签与深度剖析，并即时投影到 2D 语义画布。
            </p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="hidden"
            onChange={(e) => {
              const picked = Array.from(e.target.files ?? []);
              if (picked.length > 0) setFiles((prev) => [...prev, ...picked].slice(0, 12));
            }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="h-8 px-4 rounded-md border border-border bg-card hover:border-primary/60 text-xs font-semibold text-foreground"
          >
            选择本地图片
          </button>
        </div>

        {files.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground">待入库队列 ({files.length} 张)</span>
              <button
                type="button"
                onClick={() => setFiles([])}
                className="text-muted-foreground hover:text-foreground"
              >
                清空队列
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {files.map((f, i) => (
                <span
                  key={`${f.name}-${i}`}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary/50 px-2 py-1 text-xs text-foreground"
                >
                  <span className="max-w-[180px] truncate">{f.name}</span>
                  <button
                    type="button"
                    aria-label={`移除 ${f.name}`}
                    onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>来源/画板标签：</span>
            <input
              type="text"
              value={sourceLabel}
              onChange={(e) => setSourceLabel(e.target.value)}
              className="h-8 rounded-md border border-border bg-background px-2.5 text-xs text-foreground focus:outline-none focus:border-primary"
            />
          </label>

          <button
            type="button"
            disabled={uploading || files.length === 0}
            onClick={handleUpload}
            className="min-h-[36px] px-5 rounded-md bg-primary hover:bg-primary/90 disabled:opacity-50 text-primary-foreground text-xs font-semibold inline-flex items-center gap-1.5"
          >
            {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            <span>{uploading ? '正在分析与入库...' : `开始入库 (${files.length})`}</span>
          </button>
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/50 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive">
            {error}
          </div>
        )}

        {report && (
          <div className="rounded-lg border border-border bg-secondary/35 p-3.5 space-y-2 text-xs">
            <div className="font-bold text-foreground">
              入库完成：新增 {report.added_count} 张 · 跳过/去重 {report.skipped_count} 张 · 当前总库{' '}
              <span className="mono text-primary">{report.total_assets}</span> 张（{(report.latency_ms / 1000).toFixed(1)}s）
            </div>
            <ul className="space-y-1">
              {report.items.map((it, i) => (
                <li key={i} className="flex items-center justify-between gap-2 text-muted-foreground">
                  <span className="truncate">{it.filename}</span>
                  {it.status === 'added' ? (
                    <span className="text-primary font-medium shrink-0">
                      已入库 · {it.archetype_label} / {it.aesthetic_style_zh}（{it.title}）
                    </span>
                  ) : (
                    <span className="text-amber-600 dark:text-amber-400 shrink-0">{it.reason ?? it.status}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
