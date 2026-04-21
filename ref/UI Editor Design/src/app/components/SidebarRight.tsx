import React, { useState } from 'react';
import { Minus, Plus, Maximize2, Search, Crosshair, HelpCircle, Columns, List, MinusSquare, Type, ImageIcon } from 'lucide-react';

export function SidebarRight() {
  return (
    <div className="flex flex-col w-[300px] bg-zinc-800 border-l border-zinc-700 h-full text-sm select-none shrink-0">
      
      {/* Component Tree Header */}
      <div className="flex items-center justify-between px-2 py-1.5 bg-zinc-800 border-b border-zinc-700">
        <span className="text-xs font-semibold text-zinc-300">Component Tree</span>
        <div className="flex gap-1">
          <Minus size={14} className="text-zinc-500 hover:text-zinc-300 cursor-pointer" />
          <Plus size={14} className="text-zinc-500 hover:text-zinc-300 cursor-pointer" />
          <Maximize2 size={14} className="text-zinc-500 hover:text-zinc-300 cursor-pointer" />
        </div>
      </div>

      {/* Component Tree Content */}
      <div className="flex flex-col h-[35%] border-b border-zinc-700 overflow-y-auto bg-zinc-900 p-2">
        <TreeItem icon={<Columns size={14} className="text-blue-400" />} name="ConstraintLayout" id="main_layout" level={0} expanded />
        <TreeItem icon={<MinusSquare size={14} className="text-green-400" />} name="Button" id="btn_submit" level={1} selected />
        <TreeItem icon={<Type size={14} className="text-orange-400" />} name="TextView" id="tv_title" level={1} />
        <TreeItem icon={<Columns size={14} className="text-blue-400" />} name="LinearLayout" id="button_group" level={1} expanded />
        <TreeItem icon={<MinusSquare size={14} className="text-green-400" />} name="Button" id="btn_cancel" level={2} />
        <TreeItem icon={<ImageIcon size={14} className="text-purple-400" />} name="ImageView" id="iv_logo" level={1} />
      </div>

      {/* Attributes Header */}
      <div className="flex items-center justify-between px-2 py-1.5 bg-zinc-800 border-b border-zinc-700">
        <span className="text-xs font-semibold text-zinc-300">Attributes</span>
        <div className="flex gap-2">
          <Search size={14} className="text-zinc-500 hover:text-zinc-300 cursor-pointer" />
          <Crosshair size={14} className="text-zinc-500 hover:text-zinc-300 cursor-pointer" />
          <HelpCircle size={14} className="text-zinc-500 hover:text-zinc-300 cursor-pointer" />
        </div>
      </div>

      {/* Attributes Content */}
      <div className="flex-1 overflow-y-auto bg-zinc-900 pb-4">
        
        {/* Declared Attributes */}
        <AttributeSection title="Declared Attributes" defaultExpanded>
          <PropertyRow label="id" value="@+id/btn_submit" isText />
          <PropertyRow label="layout_width" value="wrap_content" isSelect />
          <PropertyRow label="layout_height" value="wrap_content" isSelect />
          <PropertyRow label="text" value="Submit" isText />
        </AttributeSection>

        {/* Layout Attributes */}
        <AttributeSection title="Layout" defaultExpanded>
          <div className="px-3 py-2 text-[10px] text-zinc-500 text-center border-b border-zinc-800 bg-zinc-900/50">
            {/* Visual Margin/Padding Editor Mock */}
            <div className="w-32 h-32 mx-auto border border-zinc-700 relative bg-zinc-800 flex items-center justify-center">
              <span className="absolute top-1 text-zinc-400">0</span>
              <span className="absolute bottom-1 text-zinc-400">0</span>
              <span className="absolute left-1 text-zinc-400">0</span>
              <span className="absolute right-1 text-zinc-400">0</span>
              <div className="w-20 h-20 border border-zinc-600 bg-zinc-700 relative flex items-center justify-center">
                <span className="text-xs text-zinc-300 font-mono">Button</span>
              </div>
            </div>
            <div className="mt-2 text-zinc-400">Constraint Widget</div>
          </div>
          <PropertyRow label="layout_marginTop" value="16dp" isText />
          <PropertyRow label="layout_marginStart" value="16dp" isText />
        </AttributeSection>

        {/* Common Attributes */}
        <AttributeSection title="Common Attributes" defaultExpanded>
          <PropertyRow label="text" value="Submit" isText />
          <PropertyRow label="contentDescription" value="" isText />
          <PropertyRow label="textAppearance" value="" isText />
          <PropertyRow label="fontFamily" value="sans-serif" isSelect />
          <PropertyRow label="textSize" value="14sp" isText />
          <PropertyRow label="textColor" value="@color/white" isText />
          <PropertyRow label="textStyle" value="bold" isSelect />
          <PropertyRow label="visibility" value="visible" isSelect />
          <PropertyRow label="enabled" value="true" isSelect />
          <PropertyRow label="clickable" value="true" isSelect />
        </AttributeSection>
        
        <AttributeSection title="All Attributes" defaultExpanded={false} />

      </div>
    </div>
  );
}

function TreeItem({ icon, name, id, level, expanded = false, selected = false }: { icon: React.ReactNode, name: string, id: string, level: number, expanded?: boolean, selected?: boolean }) {
  return (
    <div 
      className={`flex items-center gap-1.5 px-1 py-0.5 rounded text-xs cursor-pointer ${selected ? 'bg-blue-900/40 text-blue-200' : 'text-zinc-300 hover:bg-zinc-800'}`}
      style={{ paddingLeft: `${(level * 12) + 4}px` }}
    >
      {/* Caret placeholder */}
      <span className="w-3 flex justify-center">
        {expanded && <Minus size={10} className="text-zinc-500" />}
        {!expanded && level === 0 && <Plus size={10} className="text-zinc-500" />}
      </span>
      {icon}
      <span>{name}</span>
      <span className="text-zinc-500 ml-1 truncate max-w-[120px]"> - "{id}"</span>
    </div>
  );
}

function AttributeSection({ title, children, defaultExpanded = false }: { title: string, children?: React.ReactNode, defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  return (
    <div className="border-b border-zinc-800">
      <div 
        className="flex items-center gap-1.5 px-2 py-1 bg-zinc-800/80 cursor-pointer hover:bg-zinc-800 text-xs text-zinc-300 font-semibold"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="w-3">
          {expanded ? <Minus size={12} className="text-zinc-400" /> : <Plus size={12} className="text-zinc-400" />}
        </span>
        {title}
      </div>
      {expanded && children}
    </div>
  );
}

function PropertyRow({ label, value, isText, isSelect }: { label: string, value: string, isText?: boolean, isSelect?: boolean }) {
  return (
    <div className="flex items-center border-b border-zinc-800/50 hover:bg-zinc-800/50 group">
      <div className="w-[120px] px-3 py-1 text-xs text-zinc-400 group-hover:text-zinc-300 border-r border-zinc-800 truncate" title={label}>
        {label}
      </div>
      <div className="flex-1 px-2 py-1">
        {isText && (
          <input 
            type="text" 
            defaultValue={value} 
            className="w-full bg-transparent text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500/50 rounded px-1 -mx-1"
          />
        )}
        {isSelect && (
          <select className="w-full bg-transparent text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500/50 rounded px-1 -mx-1 appearance-none cursor-pointer">
            <option>{value}</option>
            <option>match_parent</option>
            <option>wrap_content</option>
            <option>0dp</option>
          </select>
        )}
      </div>
    </div>
  );
}
