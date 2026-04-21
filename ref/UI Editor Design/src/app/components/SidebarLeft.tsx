import { FolderTree, Component, Search, Type, Image as ImageIcon, BoxSelect, Columns, Grid3x3, CheckSquare, Settings2, SlidersHorizontal, List, ArrowRightToLine, MinusSquare, Code } from 'lucide-react';
import { useState } from 'react';

export function SidebarLeft() {
  const [activeTab, setActiveTab] = useState<'project' | 'palette'>('palette');

  return (
    <div className="flex flex-col w-[260px] bg-zinc-800 border-r border-zinc-700 h-full text-sm select-none shrink-0">
      {/* Sidebar Tabs */}
      <div className="flex bg-zinc-900 border-b border-zinc-700">
        <button 
          onClick={() => setActiveTab('project')}
          className={`flex-1 py-1.5 flex items-center justify-center gap-1 text-xs border-r border-zinc-700 ${activeTab === 'project' ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-500 hover:text-zinc-300'}`}>
          <FolderTree size={14} /> Project
        </button>
        <button 
          onClick={() => setActiveTab('palette')}
          className={`flex-1 py-1.5 flex items-center justify-center gap-1 text-xs ${activeTab === 'palette' ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-500 hover:text-zinc-300'}`}>
          <Component size={14} /> Palette
        </button>
      </div>

      {activeTab === 'palette' ? <PaletteView /> : <ProjectView />}
    </div>
  );
}

function PaletteView() {
  const categories = [
    {
      name: "Common",
      items: [
        { icon: <Type size={16} />, name: "TextView" },
        { icon: <MinusSquare size={16} />, name: "Button" },
        { icon: <ImageIcon size={16} />, name: "ImageView" },
        { icon: <BoxSelect size={16} />, name: "RecyclerView" },
      ]
    },
    {
      name: "Text",
      items: [
        { icon: <Type size={16} />, name: "Plain Text" },
        { icon: <Type size={16} />, name: "Password" },
        { icon: <Type size={16} />, name: "Email" },
        { icon: <Type size={16} />, name: "Phone" },
      ]
    },
    {
      name: "Buttons",
      items: [
        { icon: <MinusSquare size={16} />, name: "Button" },
        { icon: <ImageIcon size={16} />, name: "ImageButton" },
        { icon: <CheckSquare size={16} />, name: "CheckBox" },
        { icon: <Settings2 size={16} />, name: "Switch" },
      ]
    },
    {
      name: "Widgets",
      items: [
        { icon: <List size={16} />, name: "Spinner" },
        { icon: <SlidersHorizontal size={16} />, name: "ProgressBar" },
        { icon: <SlidersHorizontal size={16} />, name: "SeekBar" },
        { icon: <ArrowRightToLine size={16} />, name: "RatingBar" },
      ]
    },
    {
      name: "Layouts",
      items: [
        { icon: <Columns size={16} />, name: "ConstraintLayout" },
        { icon: <Columns size={16} />, name: "LinearLayout (H)" },
        { icon: <Columns size={16} className="rotate-90" />, name: "LinearLayout (V)" },
        { icon: <Grid3x3 size={16} />, name: "GridLayout" },
      ]
    }
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden bg-zinc-900">
      {/* Search Bar */}
      <div className="p-2 border-b border-zinc-800 bg-zinc-900">
        <div className="relative flex items-center">
          <Search size={14} className="absolute left-2 text-zinc-500" />
          <input 
            type="text" 
            placeholder="Search..." 
            className="w-full bg-zinc-800 text-zinc-300 rounded border border-zinc-700 pl-7 pr-2 py-1 text-xs focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Palette Categories */}
      <div className="flex flex-1 overflow-hidden">
        {/* Category List (Left thin column) */}
        <div className="w-[100px] bg-zinc-900 overflow-y-auto border-r border-zinc-800">
          {categories.map((cat, idx) => (
            <div 
              key={cat.name} 
              className={`px-3 py-1.5 text-xs cursor-pointer truncate ${idx === 0 ? 'bg-zinc-800 text-zinc-100 font-medium border-l-2 border-blue-500' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'}`}
            >
              {cat.name}
            </div>
          ))}
        </div>

        {/* Category Items (Right area) */}
        <div className="flex-1 overflow-y-auto bg-zinc-800 p-2">
          <div className="text-zinc-500 text-[11px] uppercase font-semibold mb-2">Common</div>
          <div className="flex flex-col gap-0.5">
            {categories[0].items.map(item => (
              <div key={item.name} className="flex items-center gap-2 p-1.5 hover:bg-zinc-700 rounded cursor-grab active:cursor-grabbing text-zinc-300">
                <span className="text-zinc-400">{item.icon}</span>
                <span className="text-xs">{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ProjectView() {
  return (
    <div className="flex-1 bg-zinc-900 p-2 overflow-y-auto">
      <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 hover:bg-zinc-800 cursor-pointer rounded">
        <FolderTree size={14} className="text-zinc-500" />
        <span className="font-semibold text-zinc-300">app</span>
      </div>
      <div className="pl-4 mt-1 space-y-1">
        <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 hover:bg-zinc-800 cursor-pointer rounded">
          <FolderTree size={14} className="text-zinc-500" />
          <span>manifests</span>
        </div>
        <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 hover:bg-zinc-800 cursor-pointer rounded">
          <FolderTree size={14} className="text-zinc-500" />
          <span>java</span>
        </div>
        <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 hover:bg-zinc-800 cursor-pointer rounded">
          <FolderTree size={14} className="text-zinc-500" />
          <span className="text-zinc-300">res</span>
        </div>
        <div className="pl-4 space-y-1">
          <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 hover:bg-zinc-800 cursor-pointer rounded">
            <FolderTree size={14} className="text-zinc-500" />
            <span>drawable</span>
          </div>
          <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 hover:bg-zinc-800 cursor-pointer rounded">
            <FolderTree size={14} className="text-zinc-500" />
            <span className="text-zinc-300">layout</span>
          </div>
          <div className="pl-4 space-y-1">
            <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 bg-blue-900/40 text-blue-200 cursor-pointer rounded">
              <Code size={14} className="text-orange-400" />
              <span>activity_main.xml</span>
            </div>
            <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 hover:bg-zinc-800 cursor-pointer rounded">
              <Code size={14} className="text-orange-400" />
              <span>fragment_home.xml</span>
            </div>
          </div>
          <div className="text-zinc-400 text-xs flex items-center gap-1.5 p-1 hover:bg-zinc-800 cursor-pointer rounded">
            <FolderTree size={14} className="text-zinc-500" />
            <span>values</span>
          </div>
        </div>
      </div>
    </div>
  );
}
