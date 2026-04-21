import { useState } from 'react';
import { Search, Plus, Filter, Image as ImageIcon, Type, Languages, Film, Music, Grid, List as ListIcon, Trash2, Edit3, Settings2 } from 'lucide-react';

export function ResourceManager() {
  const [activeCategory, setActiveCategory] = useState('Images');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');

  const categories = [
    { id: 'Images', icon: <ImageIcon size={14} /> },
    { id: 'Fonts', icon: <Type size={14} /> },
    { id: 'Texts', icon: <Languages size={14} /> },
    { id: 'Media', icon: <Film size={14} /> },
  ];

  const images = [
    { name: 'logo.png', format: 'ARGB8888', width: 256, height: 64, size: '64 KB' },
    { name: 'bg_main.jpg', format: 'RGB565', width: 800, height: 480, size: '750 KB' },
    { name: 'btn_normal.png', format: 'ARGB8888', width: 120, height: 40, size: '18 KB' },
    { name: 'btn_pressed.png', format: 'ARGB8888', width: 120, height: 40, size: '18 KB' },
    { name: 'ic_home.png', format: 'A8', width: 32, height: 32, size: '1 KB' },
    { name: 'ic_settings.png', format: 'A8', width: 32, height: 32, size: '1 KB' },
  ];

  const fonts = [
    { name: 'Montserrat-Regular.ttf', size: 16, bpp: 4, range: 'ASCII', memory: '45 KB' },
    { name: 'Montserrat-Bold.ttf', size: 24, bpp: 4, range: 'ASCII', memory: '68 KB' },
    { name: 'NotoSansSC-Regular.otf', size: 20, bpp: 2, range: 'Basic Latin + CJK', memory: '1.2 MB' },
    { name: 'Digital-7.ttf', size: 48, bpp: 8, range: 'Numbers', memory: '12 KB' },
  ];

  const texts = [
    { id: 'txt_welcome', en: 'Welcome', zh: '欢迎', de: 'Willkommen' },
    { id: 'txt_settings', en: 'Settings', zh: '设置', de: 'Einstellungen' },
    { id: 'txt_network', en: 'Network', zh: '网络', de: 'Netzwerk' },
    { id: 'txt_connect', en: 'Connect', zh: '连接', de: 'Verbinden' },
    { id: 'txt_error', en: 'Error', zh: '错误', de: 'Fehler' },
  ];

  return (
    <div className="flex w-full h-full bg-zinc-950 text-zinc-300 select-none font-sans">
      {/* Sidebar Categories */}
      <div className="w-[200px] bg-zinc-900 border-r border-zinc-800 flex flex-col shrink-0 shadow-sm z-10">
        <div className="px-4 py-3 text-xs font-bold text-zinc-400 uppercase tracking-widest border-b border-zinc-800/80 shadow-sm bg-zinc-900/50">
          Resource Manager
        </div>
        <div className="p-2 flex-1 overflow-y-auto space-y-1">
          {categories.map((cat) => (
            <div
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer text-sm font-medium transition-all ${
                activeCategory === cat.id
                  ? 'bg-blue-600/10 text-blue-400 shadow-[inset_2px_0_0_0_rgba(59,130,246,1)]'
                  : 'text-zinc-400 hover:bg-zinc-800/80 hover:text-zinc-200'
              }`}
            >
              <span className={activeCategory === cat.id ? 'text-blue-500' : 'text-zinc-500'}>{cat.icon}</span>
              <span>{cat.id}</span>
              <div className="ml-auto text-[10px] text-zinc-600 bg-zinc-900/50 px-1.5 py-0.5 rounded-full font-mono">
                {cat.id === 'Images' && images.length}
                {cat.id === 'Fonts' && fonts.length}
                {cat.id === 'Texts' && texts.length}
                {cat.id === 'Media' && 0}
              </div>
            </div>
          ))}
        </div>
        
        {/* Bottom stats */}
        <div className="p-4 border-t border-zinc-800/80 bg-zinc-900 text-xs text-zinc-500 space-y-1.5">
           <div className="flex justify-between"><span>Flash Usage:</span> <span className="text-zinc-300 font-mono">2.1 MB</span></div>
           <div className="flex justify-between"><span>SRAM Usage:</span> <span className="text-zinc-300 font-mono">812 KB</span></div>
           <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-2">
             <div className="bg-blue-500 h-full w-[45%]"></div>
           </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 overflow-hidden bg-zinc-950">
        {/* Toolbar */}
        <div className="h-12 border-b border-zinc-800/80 bg-zinc-900/50 flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded text-xs font-medium transition-colors shadow-sm">
              <Plus size={14} />
              <span>Import {activeCategory}</span>
            </button>
            <div className="w-px h-5 bg-zinc-700/50 mx-2"></div>
            <button className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors" title="Edit Properties">
              <Edit3 size={15} />
            </button>
            <button className="p-1.5 text-zinc-400 hover:text-red-400 hover:bg-zinc-800 rounded transition-colors" title="Delete Selected">
              <Trash2 size={15} />
            </button>
            <button className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors" title="Advanced Settings">
              <Settings2 size={15} />
            </button>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative group">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500 group-focus-within:text-blue-400 transition-colors" />
              <input
                type="text"
                placeholder={`Filter ${activeCategory.toLowerCase()}...`}
                className="bg-zinc-950 border border-zinc-800 rounded-md pl-8 pr-3 py-1.5 text-xs w-64 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 text-zinc-200 placeholder:text-zinc-600 transition-all shadow-inner"
              />
            </div>
            
            {activeCategory !== 'Texts' && (
              <div className="flex items-center bg-zinc-950 border border-zinc-800 rounded-md p-0.5 shadow-inner">
                <button 
                  onClick={() => setViewMode('grid')}
                  className={`p-1.5 rounded-sm transition-colors ${viewMode === 'grid' ? 'bg-zinc-800 text-zinc-100 shadow-sm' : 'text-zinc-500 hover:text-zinc-300'}`}
                  title="Grid View"
                >
                  <Grid size={14} />
                </button>
                <button 
                  onClick={() => setViewMode('list')}
                  className={`p-1.5 rounded-sm transition-colors ${viewMode === 'list' ? 'bg-zinc-800 text-zinc-100 shadow-sm' : 'text-zinc-500 hover:text-zinc-300'}`}
                  title="List View"
                >
                  <ListIcon size={14} />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Content View */}
        <div className="flex-1 overflow-y-auto p-4 bg-zinc-950/80">
          
          {/* IMAGES */}
          {activeCategory === 'Images' && viewMode === 'list' && (
            <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900 shadow-sm">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-zinc-800/80 text-zinc-400 border-b border-zinc-800 text-xs uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 font-semibold w-10 text-center"><input type="checkbox" className="rounded border-zinc-700 bg-zinc-900 accent-blue-500 cursor-pointer" /></th>
                    <th className="px-4 py-3 font-semibold">Preview</th>
                    <th className="px-4 py-3 font-semibold">Name</th>
                    <th className="px-4 py-3 font-semibold">Format</th>
                    <th className="px-4 py-3 font-semibold">Dimensions</th>
                    <th className="px-4 py-3 font-semibold text-right">C Array Size</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {images.map((img, i) => (
                    <tr key={i} className="hover:bg-zinc-800/50 transition-colors group cursor-default">
                      <td className="px-4 py-3 text-center"><input type="checkbox" className="rounded border-zinc-700 bg-zinc-900 accent-blue-500 cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity" /></td>
                      <td className="px-4 py-3">
                        <div className="w-10 h-10 rounded border border-zinc-700/50 bg-zinc-950/50 flex items-center justify-center">
                          <ImageIcon size={20} className="text-zinc-600" />
                        </div>
                      </td>
                      <td className="px-4 py-3 font-medium text-zinc-200">{img.name}</td>
                      <td className="px-4 py-3">
                        <span className="bg-zinc-800 border border-zinc-700 text-zinc-300 px-2 py-0.5 rounded text-xs font-mono">{img.format}</span>
                      </td>
                      <td className="px-4 py-3 text-zinc-400 font-mono text-xs">{img.width} × {img.height}</td>
                      <td className="px-4 py-3 text-right text-zinc-400 font-mono text-xs">{img.size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeCategory === 'Images' && viewMode === 'grid' && (
             <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-4">
              {images.map((img, i) => (
                <div key={i} className="group border border-zinc-800 bg-zinc-900 rounded-lg overflow-hidden hover:border-blue-500/50 hover:shadow-[0_0_0_1px_rgba(59,130,246,0.3)] transition-all cursor-pointer">
                   <div className="h-28 bg-zinc-950/50 border-b border-zinc-800/50 flex items-center justify-center p-4 relative">
                      <div className="absolute top-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity">
                         <input type="checkbox" className="rounded border-zinc-700 bg-zinc-900 accent-blue-500 cursor-pointer" />
                      </div>
                      <ImageIcon size={40} className="text-zinc-600 group-hover:text-zinc-500 transition-colors" />
                   </div>
                   <div className="p-3">
                      <div className="font-medium text-sm text-zinc-200 truncate" title={img.name}>{img.name}</div>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-[10px] text-zinc-500 font-mono">{img.width}×{img.height}</span>
                        <span className="text-[10px] bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-400 font-mono">{img.format}</span>
                      </div>
                   </div>
                </div>
              ))}
             </div>
          )}

          {/* FONTS */}
          {activeCategory === 'Fonts' && (
            <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900 shadow-sm">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-zinc-800/80 text-zinc-400 border-b border-zinc-800 text-xs uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 font-semibold w-10 text-center"><input type="checkbox" className="rounded border-zinc-700 bg-zinc-900 accent-blue-500 cursor-pointer" /></th>
                    <th className="px-4 py-3 font-semibold">Font File</th>
                    <th className="px-4 py-3 font-semibold">Size (px)</th>
                    <th className="px-4 py-3 font-semibold">BPP</th>
                    <th className="px-4 py-3 font-semibold">Characters</th>
                    <th className="px-4 py-3 font-semibold text-right">Memory Size</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {fonts.map((font, i) => (
                    <tr key={i} className="hover:bg-zinc-800/50 transition-colors group cursor-default">
                      <td className="px-4 py-3 text-center"><input type="checkbox" className="rounded border-zinc-700 bg-zinc-900 accent-blue-500 cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity" /></td>
                      <td className="px-4 py-3 font-medium text-zinc-200 flex items-center gap-2">
                        <Type size={16} className="text-zinc-500" />
                        {font.name}
                      </td>
                      <td className="px-4 py-3">
                         <span className="text-zinc-300 font-mono">{font.size}</span>
                      </td>
                      <td className="px-4 py-3 text-zinc-400 font-mono text-xs">{font.bpp} bit</td>
                      <td className="px-4 py-3">
                         <span className="bg-zinc-800 border border-zinc-700 text-zinc-300 px-2 py-0.5 rounded text-xs">{font.range}</span>
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-400 font-mono text-xs">{font.memory}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* TEXTS / TRANSLATIONS */}
          {activeCategory === 'Texts' && (
            <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900 shadow-sm flex flex-col h-full">
              <div className="flex-1 overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-800/80 text-zinc-400 border-b border-zinc-800 text-xs uppercase tracking-wider sticky top-0 z-10 backdrop-blur-sm">
                    <tr>
                      <th className="px-4 py-3 font-semibold w-10 text-center"><input type="checkbox" className="rounded border-zinc-700 bg-zinc-900 accent-blue-500 cursor-pointer" /></th>
                      <th className="px-4 py-3 font-semibold text-blue-400">ID (Key)</th>
                      <th className="px-4 py-3 font-semibold">English (en)</th>
                      <th className="px-4 py-3 font-semibold">Chinese (zh)</th>
                      <th className="px-4 py-3 font-semibold">German (de)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {texts.map((txt, i) => (
                      <tr key={i} className="hover:bg-zinc-800/50 transition-colors group">
                        <td className="px-4 py-3 text-center"><input type="checkbox" className="rounded border-zinc-700 bg-zinc-900 accent-blue-500 cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity" /></td>
                        <td className="px-4 py-3 font-mono text-xs text-blue-400/90">{txt.id}</td>
                        <td className="px-4 py-3">
                          <input type="text" defaultValue={txt.en} className="w-full bg-transparent border border-transparent hover:border-zinc-700 focus:border-blue-500 focus:bg-zinc-950 rounded px-2 py-1 text-sm text-zinc-200 outline-none transition-all" />
                        </td>
                        <td className="px-4 py-3">
                          <input type="text" defaultValue={txt.zh} className="w-full bg-transparent border border-transparent hover:border-zinc-700 focus:border-blue-500 focus:bg-zinc-950 rounded px-2 py-1 text-sm text-zinc-200 outline-none transition-all" />
                        </td>
                        <td className="px-4 py-3">
                          <input type="text" defaultValue={txt.de} className="w-full bg-transparent border border-transparent hover:border-zinc-700 focus:border-blue-500 focus:bg-zinc-950 rounded px-2 py-1 text-sm text-zinc-200 outline-none transition-all" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* MEDIA EMPTY STATE */}
          {activeCategory === 'Media' && (
            <div className="flex flex-col items-center justify-center h-full text-zinc-500 space-y-4">
              <div className="w-20 h-20 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center shadow-inner">
                <Film size={32} className="text-zinc-600" />
              </div>
              <div className="text-center">
                <h3 className="text-lg font-medium text-zinc-300 mb-1">No Media Files</h3>
                <p className="text-sm text-zinc-500 max-w-sm">Import video or audio files to use them as resources in your embedded UI application.</p>
              </div>
              <button className="mt-4 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors shadow-sm">
                Import Media
              </button>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
