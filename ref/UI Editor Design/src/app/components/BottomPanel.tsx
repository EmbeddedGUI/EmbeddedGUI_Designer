import React, { useState } from 'react';
import { Terminal, Bug, Play, Info, CheckCircle2, XCircle, AlertTriangle, ChevronUp, ChevronDown } from 'lucide-react';

export function BottomPanel() {
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState('Build');

  return (
    <div className="flex flex-col border-t border-zinc-700 bg-zinc-800 text-zinc-300 select-none shrink-0">
      
      {/* Panel Headers / Tabs */}
      <div className="flex items-center px-1 h-7 text-xs">
        <div className="flex items-center gap-1 h-full">
          <PanelTab 
            icon={<Terminal size={14} className="text-zinc-400" />} 
            name="Run" 
            isActive={activeTab === 'Run'} 
            onClick={() => { setActiveTab('Run'); setExpanded(true); }} 
          />
          <PanelTab 
            icon={<CheckCircle2 size={14} className="text-green-500" />} 
            name="Build" 
            isActive={activeTab === 'Build'} 
            onClick={() => { setActiveTab('Build'); setExpanded(true); }} 
          />
          <PanelTab 
            icon={<Bug size={14} className="text-zinc-400" />} 
            name="Debug" 
            isActive={activeTab === 'Debug'} 
            onClick={() => { setActiveTab('Debug'); setExpanded(true); }} 
          />
          <PanelTab 
            icon={<Info size={14} className="text-blue-400" />} 
            name="Logcat" 
            isActive={activeTab === 'Logcat'} 
            onClick={() => { setActiveTab('Logcat'); setExpanded(true); }} 
          />
        </div>
        
        <div className="flex-1" />
        
        {/* Actions / Toggle */}
        <div className="flex items-center gap-2 px-2">
          <span className="text-zinc-500">Event Log</span>
          <span className="text-zinc-500">Device File Explorer</span>
          <button 
            className="p-1 hover:bg-zinc-700 rounded text-zinc-400 ml-2 transition-transform" 
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      </div>

      {/* Expanded Content Area */}
      {expanded && (
        <div className="h-48 border-t border-zinc-700 bg-zinc-950 flex flex-col font-mono text-xs overflow-hidden">
          {/* Action bar for the active panel */}
          <div className="flex bg-zinc-900 border-b border-zinc-800 px-2 py-1 items-center gap-2">
            <Play size={14} className="text-green-500 cursor-pointer" />
            <XCircle size={14} className="text-red-500 cursor-pointer" />
            <span className="text-zinc-500 ml-2">app:assembleDebug</span>
          </div>
          
          {/* Log Output */}
          <div className="flex-1 overflow-y-auto p-2 text-zinc-400 leading-snug">
            {activeTab === 'Build' && (
              <>
                <div className="text-green-400">BUILD SUCCESSFUL in 1s</div>
                <div>29 actionable tasks: 29 executed</div>
                <br />
                <div>Configuration on demand is an incubating feature.</div>
                <div>&gt; Task :app:preBuild UP-TO-DATE</div>
                <div>&gt; Task :app:preDebugBuild UP-TO-DATE</div>
                <div>&gt; Task :app:compileDebugAidl NO-SOURCE</div>
                <div>&gt; Task :app:compileDebugRenderscript NO-SOURCE</div>
                <div>&gt; Task :app:generateDebugBuildConfig UP-TO-DATE</div>
                <div>&gt; Task :app:checkDebugAarMetadata UP-TO-DATE</div>
                <div>&gt; Task :app:generateDebugResValues UP-TO-DATE</div>
                <div>&gt; Task :app:generateDebugResources UP-TO-DATE</div>
                <div>&gt; Task :app:mergeDebugResources UP-TO-DATE</div>
                <div>&gt; Task :app:createDebugCompatibleScreenManifests UP-TO-DATE</div>
                <div>&gt; Task :app:extractDeepLinksDebug UP-TO-DATE</div>
                <div>&gt; Task :app:processDebugMainManifest UP-TO-DATE</div>
                <div>&gt; Task :app:processDebugManifest UP-TO-DATE</div>
                <div>&gt; Task :app:processDebugManifestForPackage UP-TO-DATE</div>
                <div>&gt; Task :app:processDebugResources UP-TO-DATE</div>
                <div>&gt; Task :app:compileDebugJavaWithJavac UP-TO-DATE</div>
              </>
            )}
            {activeTab === 'Logcat' && (
              <>
                <div className="flex gap-2"><span className="text-blue-400 w-12">I</span><span className="text-zinc-500 w-32">12:34:56.789</span><span>ActivityManager: Start proc com.example.app for activity...</span></div>
                <div className="flex gap-2"><span className="text-blue-400 w-12">I</span><span className="text-zinc-500 w-32">12:34:57.102</span><span>zygote64: Late-enabling -Xcheck:jni</span></div>
                <div className="flex gap-2"><span className="text-yellow-400 w-12">W</span><span className="text-zinc-500 w-32">12:34:57.450</span><span>ActivityThread: Application com.example.app is waiting for the debugger on port 8100...</span></div>
                <div className="flex gap-2"><span className="text-green-400 w-12">D</span><span className="text-zinc-500 w-32">12:34:58.201</span><span>NetworkSecurityConfig: No Network Security Config specified, using platform default</span></div>
                <div className="flex gap-2"><span className="text-red-400 w-12">E</span><span className="text-zinc-500 w-32">12:35:01.005</span><span>EGL_emulation: eglMakeCurrent: 0xebfae9c0: ver 3 0 (tinfo 0xeb123450)</span></div>
              </>
            )}
          </div>
        </div>
      )}
      
      {/* Footer Status Line */}
      <div className="h-6 flex items-center justify-between px-3 text-[11px] bg-zinc-800 border-t border-zinc-700">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1 cursor-pointer hover:text-zinc-100">
             <AlertTriangle size={12} className="text-yellow-500" /> 1 Warning
          </span>
          <span className="text-zinc-500 cursor-pointer hover:text-zinc-300">Git: main</span>
          <span className="text-zinc-500 cursor-pointer hover:text-zinc-300">UTF-8</span>
          <span className="text-zinc-500 cursor-pointer hover:text-zinc-300">2 spaces</span>
        </div>
        <div className="flex items-center gap-4 text-zinc-500">
          <span>Memory: 450 of 2048M</span>
          <span>Gradle sync finished in 2s</span>
        </div>
      </div>
    </div>
  );
}

function PanelTab({ icon, name, isActive, onClick }: { icon: React.ReactNode, name: string, isActive: boolean, onClick: () => void }) {
  return (
    <div 
      className={`flex items-center gap-1.5 h-full px-3 cursor-pointer border-r border-zinc-700 ${isActive ? 'bg-zinc-700/50 text-zinc-200 font-medium border-t-2 border-t-blue-500' : 'hover:bg-zinc-700/30 border-t-2 border-t-transparent'}`}
      onClick={onClick}
    >
      {icon}
      <span>{name}</span>
    </div>
  );
}
