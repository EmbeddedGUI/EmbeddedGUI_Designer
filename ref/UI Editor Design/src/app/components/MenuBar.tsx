import { Menu } from 'lucide-react';

export function MenuBar() {
  const menuItems = ["File", "Edit", "View", "Navigate", "Code", "Refactor", "Build", "Run", "Tools", "Window", "Help"];

  return (
    <div className="flex items-center px-2 py-1 bg-zinc-900 text-zinc-300 text-[13px] border-b border-zinc-700/50 select-none">
      <div className="flex items-center gap-4">
        <Menu size={16} className="text-zinc-400 hover:text-zinc-100 cursor-pointer transition-colors" />
        <div className="flex gap-4">
          {menuItems.map((item) => (
            <span key={item} className="hover:text-zinc-100 hover:bg-zinc-800 px-2 py-0.5 rounded cursor-pointer transition-colors">
              {item}
            </span>
          ))}
        </div>
      </div>
      <div className="ml-auto text-zinc-500 text-xs">
        EmbeddedGUI Designer
      </div>
    </div>
  );
}
