import React from 'react';
import type { CadDetailDiagram } from '../types/tectonic';

interface CadDetailViewerProps {
  detail: CadDetailDiagram | null;
  drawingCode: string;
  assemblyName: string;
  layers: string[];
}

export const CadDetailViewer: React.FC<CadDetailViewerProps> = ({
  detail,
  drawingCode,
  assemblyName,
  layers,
}) => {
  return (
    <div className="border border-[#E2E5EA] bg-[#FFFFFF] p-4 sm:p-5 space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2 pb-3 border-b border-[#E2E5EA]">
        <div className="space-y-0.5 min-w-0">
          <h3 className="font-display text-sm font-bold text-[#0E1015] truncate">
            {detail?.title ?? assemblyName}
          </h3>
          <p className="text-xs text-[#525866]">匹配标准构造节点详图与工程分层清单</p>
        </div>
        <span className="mono text-xs font-semibold text-[#153CE8] shrink-0">{drawingCode}</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
        <div className="md:col-span-6 border border-[#E2E5EA] bg-[#FAFBFD] p-2">
          {detail?.svg ? (
            <div
              className="w-full [&_svg]:w-full [&_svg]:h-auto [&_svg]:block"
              dangerouslySetInnerHTML={{ __html: detail.svg }}
            />
          ) : (
            <div className="aspect-[16/10] flex items-center justify-center text-xs text-[#525866]">
              标准构造剖面详图（索引 {drawingCode}）
            </div>
          )}
        </div>

        <div className="md:col-span-6 space-y-2.5 text-xs">
          <div className="font-semibold text-[#0E1015]">标准分层构造栈 ({assemblyName})</div>
          <ol className="space-y-2 border-t border-[#E2E5EA] pt-2.5">
            {layers.map((layer, idx) => (
              <li key={idx} className="flex items-start gap-2.5 text-[#525866] leading-relaxed">
                <span className="mono font-semibold text-[#0E1015] shrink-0">
                  0{idx + 1}
                </span>
                <span>{layer}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
};
