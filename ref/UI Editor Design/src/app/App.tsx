import React from 'react';
import { MenuBar } from './components/MenuBar';
import { Toolbar } from './components/Toolbar';
import { SidebarLeft } from './components/SidebarLeft';
import { Workspace } from './components/Workspace';
import { SidebarRight } from './components/SidebarRight';
import { BottomPanel } from './components/BottomPanel';

export default function App() {
  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-zinc-950 font-sans text-zinc-300 antialiased">
      {/* Top Application Bar */}
      <div className="flex flex-col shrink-0">
        <MenuBar />
        <Toolbar />
      </div>

      {/* Main Ide Body */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Panels (Project / Palette) */}
        <SidebarLeft />
        
        {/* Central Workspace (Canvas / Editor) */}
        <Workspace />
        
        {/* Right Panels (Component Tree / Attributes) */}
        <SidebarRight />
      </div>

      {/* Bottom Information / Build Status Panel */}
      <BottomPanel />
    </div>
  );
}
