import { Play, Square, Pause, RotateCw, Smartphone, List, Layers, Code, SplitSquareHorizontal, Layout, Type, Image as ImageIcon, AlignLeft, BoxSelect, SquareDashedBottom, Grid3x3 } from 'lucide-react';

export function Toolbar() {
  return (
    <div className="flex items-center px-2 py-1.5 bg-zinc-800 text-zinc-300 border-b border-zinc-700 select-none shadow-sm">
      {/* Project Actions */}
      <div className="flex items-center gap-1 border-r border-zinc-700 pr-2 mr-2">
        <button className="p-1 hover:bg-zinc-700 rounded text-zinc-400 hover:text-green-500 transition-colors" title="Run 'app'">
          <Play size={16} fill="currentColor" />
        </button>
        <button className="p-1 hover:bg-zinc-700 rounded text-zinc-400 hover:text-yellow-500 transition-colors" title="Debug 'app'">
          <BugIcon />
        </button>
        <button className="p-1 hover:bg-zinc-700 rounded text-zinc-500 hover:text-red-500 transition-colors" title="Stop">
          <Square size={16} fill="currentColor" />
        </button>
        <button className="p-1 hover:bg-zinc-700 rounded text-zinc-400 hover:text-zinc-100 transition-colors" title="Apply Changes">
          <RotateCw size={16} />
        </button>
      </div>

      {/* Device Config */}
      <div className="flex items-center gap-2 border-r border-zinc-700 pr-2 mr-2">
        <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-0.5 text-xs cursor-pointer hover:bg-zinc-800">
          <Smartphone size={14} className="text-zinc-400" />
          <span>Pixel 6 API 33</span>
        </div>
        <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-0.5 text-xs cursor-pointer hover:bg-zinc-800">
          <span className="text-zinc-400">Theme</span>
        </div>
        <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-0.5 text-xs cursor-pointer hover:bg-zinc-800">
          <span className="text-zinc-400">en-US</span>
        </div>
      </div>

      <div className="flex-1" />

      {/* View Toggles */}
      <div className="flex items-center gap-0.5 bg-zinc-900 rounded p-0.5 border border-zinc-700">
        <button className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-700 text-zinc-100 text-xs">
          <Code size={14} /> Code
        </button>
        <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-100 text-xs transition-colors">
          <SplitSquareHorizontal size={14} /> Split
        </button>
        <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-100 text-xs transition-colors">
          <Layout size={14} /> Design
        </button>
      </div>
    </div>
  );
}

function BugIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m8 2 1.88 1.88"/>
      <path d="M14.12 3.88 16 2"/>
      <path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/>
      <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/>
      <path d="M12 20v-9"/>
      <path d="M6.53 9C4.6 8.8 3 7.1 3 5"/>
      <path d="M6 13H2"/>
      <path d="M3 21c0-2.1 1.7-3.9 3.8-4"/>
      <path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/>
      <path d="M22 13h-4"/>
      <path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/>
    </svg>
  );
}