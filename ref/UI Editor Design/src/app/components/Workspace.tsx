import { ZoomIn, ZoomOut, Maximize, MousePointer2, Smartphone, Type, Image as ImageIcon, CheckSquare, Settings2, Hand, MinusSquare, X, Smartphone as SmartphoneIcon } from 'lucide-react';
import { useState } from 'react';
import { ResourceManager } from './ResourceManager';

export function Workspace() {
  const [zoom, setZoom] = useState(100);
  const [activeTab, setActiveTab] = useState<'editor' | 'resources'>('resources');

  return (
    <div className="flex flex-col flex-1 bg-zinc-950 overflow-hidden relative">
      
      {/* Workspace Toolbar / Tabs */}
      <div className="flex items-center justify-between bg-zinc-800/80 border-b border-zinc-700/50 absolute top-0 w-full z-10 backdrop-blur-sm shadow-sm h-8 shrink-0">
        
        {/* Editor Tabs */}
        <div className="flex items-center text-xs h-full">
          <div 
            className={`flex items-center gap-2 px-3 h-full cursor-pointer border-r border-zinc-700 transition-colors select-none ${activeTab === 'editor' ? 'bg-zinc-900 border-t-2 border-t-blue-500 text-zinc-100' : 'hover:bg-zinc-700/50 border-t-2 border-t-transparent text-zinc-400'}`}
            onClick={() => setActiveTab('editor')}
          >
            <span className="font-mono">activity_main.xml</span>
            <X size={12} className="hover:bg-zinc-600 rounded-sm" />
          </div>
          <div 
            className={`flex items-center gap-2 px-3 h-full cursor-pointer border-r border-zinc-700 transition-colors select-none ${activeTab === 'resources' ? 'bg-zinc-900 border-t-2 border-t-blue-500 text-zinc-100' : 'hover:bg-zinc-700/50 border-t-2 border-t-transparent text-zinc-400'}`}
            onClick={() => setActiveTab('resources')}
          >
            <span>Resource Manager</span>
            <X size={12} className="hover:bg-zinc-600 rounded-sm" />
          </div>
        </div>

        {/* View Controls - only visible when editing a layout */}
        {activeTab === 'editor' && (
          <div className="flex items-center gap-2 px-3">
            <button className="p-1 hover:bg-zinc-700 rounded text-zinc-400" title="Select Tool">
              <MousePointer2 size={14} />
            </button>
            <button className="p-1 hover:bg-zinc-700 rounded text-zinc-400" title="Pan Tool">
              <Hand size={14} />
            </button>
            <div className="w-px h-4 bg-zinc-700 mx-1" />
            <button className="p-1 hover:bg-zinc-700 rounded text-zinc-400" onClick={() => setZoom(z => Math.max(10, z - 10))}>
              <ZoomOut size={14} />
            </button>
            <span className="text-zinc-300 text-xs min-w-[3rem] text-center select-none">{zoom}%</span>
            <button className="p-1 hover:bg-zinc-700 rounded text-zinc-400" onClick={() => setZoom(z => Math.min(400, z + 10))}>
              <ZoomIn size={14} />
            </button>
            <button className="p-1 hover:bg-zinc-700 rounded text-zinc-400" title="Fit to Screen">
              <Maximize size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-auto pt-8 flex">
        {activeTab === 'resources' ? (
          <ResourceManager />
        ) : (
          <div className="flex-1 flex items-center justify-center p-8 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMCIgaGVpZ2h0PSIyMCI+PHBhdGggZD0iTTAgMGgyMHYyMEgwVjB6bTEwIDEwaDEwdjEwaC0xMFYxMHpNMCAxMGgxMHYxMEgwVjEweiIgZmlsbD0iIzIyMiIgZmlsbC1vcGFjaXR5PSIuMSIvPjwvc3ZnPg==')]">
            {/* Simulated Device Screen */}
            <div 
              className="relative bg-white shadow-2xl overflow-hidden ring-1 ring-zinc-700 transition-transform origin-center select-none"
              style={{ 
                width: '412px', 
                height: '915px', 
                transform: `scale(${zoom / 100})`,
                borderRadius: '24px' // Device corners
              }}
            >
              {/* Status Bar */}
              <div className="h-6 bg-zinc-900 flex items-center justify-between px-4 text-white text-[10px]">
                <span>12:00</span>
                <div className="flex gap-1">
                  <span>5G</span>
                  <span>100%</span>
                </div>
              </div>

              {/* App Content (EmbeddedGUI preview) */}
              <div className="h-full bg-slate-50 relative flex flex-col">
                
                {/* Action Bar */}
                <div className="h-14 bg-blue-600 flex items-center px-4 shadow-sm">
                  <span className="text-white font-medium text-lg">My Application</span>
                </div>

                {/* Design Surface */}
                <div className="flex-1 p-4 flex flex-col items-center justify-center relative">
                  
                  {/* Simulated UI Widgets */}
                  <div className="absolute inset-0 pointer-events-none ring-1 ring-blue-500/30 ring-inset"></div>
                  
                  {/* Selected Widget Highlight */}
                  <div className="relative group p-2 mb-6">
                    <div className="absolute -inset-1 border-2 border-blue-500 rounded z-10 pointer-events-none">
                      {/* Resize handles */}
                      <div className="absolute -top-1.5 -left-1.5 w-3 h-3 bg-white border border-blue-500 rounded-full"></div>
                      <div className="absolute -top-1.5 left-1/2 -ml-1.5 w-3 h-3 bg-white border border-blue-500 rounded-full"></div>
                      <div className="absolute -top-1.5 -right-1.5 w-3 h-3 bg-white border border-blue-500 rounded-full"></div>
                      <div className="absolute top-1/2 -right-1.5 -mt-1.5 w-3 h-3 bg-white border border-blue-500 rounded-full"></div>
                      <div className="absolute -bottom-1.5 -right-1.5 w-3 h-3 bg-white border border-blue-500 rounded-full"></div>
                      <div className="absolute -bottom-1.5 left-1/2 -ml-1.5 w-3 h-3 bg-white border border-blue-500 rounded-full"></div>
                      <div className="absolute -bottom-1.5 -left-1.5 w-3 h-3 bg-white border border-blue-500 rounded-full"></div>
                      <div className="absolute top-1/2 -left-1.5 -mt-1.5 w-3 h-3 bg-white border border-blue-500 rounded-full"></div>
                    </div>
                    <div className="w-64 bg-white rounded-md shadow-sm border border-slate-300 overflow-hidden">
                      <div className="h-40 bg-slate-200 flex items-center justify-center text-slate-400">
                         <ImageIcon size={48} />
                      </div>
                      <div className="p-4">
                        <h3 className="font-semibold text-slate-800 text-lg mb-1">Welcome Screen</h3>
                        <p className="text-slate-500 text-sm mb-4">Design your EmbeddedGUI interface here.</p>
                      </div>
                    </div>
                  </div>

                  {/* Button Widget */}
                  <button className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-8 rounded shadow-sm hover:shadow transition-all relative group">
                    <div className="absolute -inset-1 border border-blue-400 opacity-0 group-hover:opacity-100 rounded z-10 pointer-events-none dashed"></div>
                    SUBMIT
                  </button>
                  
                  {/* Guidelines / Constraints mock */}
                  <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 5 }}>
                    {/* Horizontal line */}
                    <line x1="0" y1="45%" x2="100%" y2="45%" stroke="#3b82f6" strokeWidth="1" strokeDasharray="4 4" opacity="0.3" />
                    {/* Vertical line */}
                    <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#3b82f6" strokeWidth="1" strokeDasharray="4 4" opacity="0.3" />
                    
                    {/* Constraint lines */}
                    <line x1="50%" y1="200" x2="50%" y2="280" stroke="#3b82f6" strokeWidth="1.5" markerEnd="url(#arrow)" />
                    <path d="M 50% 240 Q 60% 240 70% 240" stroke="#3b82f6" strokeWidth="1.5" fill="none" opacity="0.5" />
                    <circle cx="50%" cy="200" r="4" fill="white" stroke="#3b82f6" strokeWidth="1.5" />
                  </svg>

                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* SVG Definitions for constraints */}
      {activeTab === 'editor' && (
        <svg width="0" height="0" className="absolute">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
            </marker>
          </defs>
        </svg>
      )}
    </div>
  );
}
