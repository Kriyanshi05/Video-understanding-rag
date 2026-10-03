import re

with open('web/app/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Home component background and splash screen
content = content.replace('bg-[#F4F1EA]', 'bg-transparent')
content = content.replace('bg-[#FAF8F5]', 'bg-white')

# Fix splash screen back to transparent -> #FAF9F5
content = content.replace('fixed inset-0 z-[100] bg-transparent', 'fixed inset-0 z-[100] bg-[#FAF9F5]')

# Clean Header Bar
content = re.sub(
    r'<header className="fixed top-0 left-0 right-0 h-20 bg-transparent border-b-4 border-\[\#121212\] z-50 flex items-center justify-between px-8">',
    '<header className="fixed top-0 left-0 right-0 h-20 bg-[#FAF9F5] border-b-2 border-black z-50 flex items-center justify-between px-8">',
    content
)

# New Video Button -> rounded-full, orange, hard shadow
content = re.sub(
    r'className="flex items-center gap-2 text-xs font-black uppercase text-\[\#121212\] bg-white border-2 border-\[\#121212\] shadow-\[3px_3px_0px_0px_\#121212\] hover:translate-x-\[2px\] hover:translate-y-\[2px\] hover:shadow-\[1px_1px_0px_0px_\#121212\] px-4 py-2 transition-all"',
    'className="flex items-center gap-2 text-xs font-black uppercase text-white bg-[#FF4D00] border-2 border-black rounded-full shadow-[3px_3px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none px-4 py-2 transition-all"',
    content
)

# IngestZone Upload / Submit buttons
content = content.replace(
    'className="w-full py-4 bg-[#121212] hover:bg-[#333] disabled:bg-transparent disabled:text-[#121212]/40 disabled:border-[#121212]/20 text-white font-extrabold uppercase tracking-widest rounded-md border-2 border-[#121212] shadow-[4px_4px_0px_0px_#121212] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#121212] disabled:shadow-none disabled:translate-x-0 disabled:translate-y-0 transition-all duration-150"',
    'className="w-full py-4 bg-[#FF4D00] disabled:bg-gray-300 disabled:text-gray-500 disabled:border-black text-white font-extrabold uppercase tracking-widest rounded-full border-2 border-black shadow-[3px_3px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none disabled:shadow-none disabled:translate-x-0 disabled:translate-y-0 transition-all duration-150"'
)

# Chat Message Bubbles
content = re.sub(
    r'className={`max-w-\[85\%\] rounded-md px-5 py-4 border-2 border-\[\#121212\] relative \$\{\n\s*msg.role === "user"\n\s*\? "bg-\[\#121212\] text-white shadow-\[3px_3px_0px_0px_\#666\]"\n\s*: "bg-white text-\[\#121212\] shadow-\[3px_3px_0px_0px_\#121212\]"\n\s*\}`\}',
    'className={`max-w-[85%] px-5 py-4 border-2 border-black relative ${msg.role === "user" ? "bg-[#000000] text-white rounded-2xl rounded-tr-none shadow-[2px_2px_0px_0px_#888]" : "bg-white text-black rounded-2xl rounded-tl-none shadow-[3px_3px_0px_0px_#000000]"}`}',
    content
)

# Avatar
content = re.sub(
    r'className={`w-10 h-10 rounded-md flex-shrink-0 flex items-center justify-center border-2 border-\[\#121212\] shadow-\[2px_2px_0px_0px_\#121212\] \$\{\n\s*msg.role === "user"\n\s*\? "bg-\[\#121212\] text-white"\n\s*: "bg-white text-\[\#121212\]"\n\s*\}`\}',
    'className={`w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center border-2 border-black shadow-[2px_2px_0px_0px_#000000] ${msg.role === "user" ? "bg-black text-white" : "bg-white text-black"}`}',
    content
)


# BROWSER WINDOW CONTAINER MOCKUP
old_video_workspace = """  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 h-[75vh] min-h-[600px]">"""

new_video_workspace = """  return (
    <div className="bg-white border-2 border-black rounded-2xl shadow-[5px_5px_0px_0px_#000000] overflow-hidden flex flex-col h-[75vh] min-h-[600px]">
      {/* Browser Header Bar */}
      <div className="bg-white border-b-2 border-black px-4 py-3 flex items-center justify-between z-20">
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500 border border-black"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-400 border border-black"></div>
          <div className="w-3 h-3 rounded-full bg-green-500 border border-black"></div>
        </div>
        <div className="bg-gray-100 border-2 border-black rounded-full px-4 py-1 text-xs font-mono font-bold text-black flex items-center justify-center">
          video-rag.local
        </div>
        <div className="w-12"></div>
      </div>
      
      {/* Main Content Area */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">"""

content = content.replace(old_video_workspace, new_video_workspace)
content = content.replace("""        </div>
      </div>
    </div>
  );""", """        </div>
      </div>
    </div>
    </div>
  );""")

content = content.replace(
    '<div className="lg:col-span-5 flex flex-col bg-white rounded-xl border-2 border-[#121212] shadow-[4px_4px_0px_0px_#121212]">',
    '<div className="lg:col-span-5 flex flex-col bg-white border-r-2 border-black">'
)
content = content.replace(
    '<div className="lg:col-span-7 flex flex-col h-full bg-white rounded-xl border-2 border-[#121212] shadow-[4px_4px_0px_0px_#121212] overflow-hidden">',
    '<div className="lg:col-span-7 flex flex-col h-full bg-white overflow-hidden">'
)

content = content.replace(
    'className="px-4 py-2 bg-white text-[#121212] border-2 border-[#121212] shadow-[3px_3px_0px_0px_#121212] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0px_0px_#121212] rounded-md text-xs font-extrabold uppercase transition-all duration-150 flex items-center gap-2"',
    'className="px-4 py-2 bg-[#FF4D00] text-white border-2 border-black shadow-[3px_3px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none rounded-full text-xs font-extrabold uppercase transition-all duration-150 flex items-center gap-2"'
)

content = content.replace(
    'className="absolute right-2.5 p-2.5 bg-[#121212] hover:bg-[#333] disabled:opacity-50 disabled:pointer-events-none text-white rounded-md border-2 border-[#121212] shadow-[2px_2px_0px_0px_#121212] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[1px_1px_0px_0px_#121212] active:scale-95 transition-all"',
    'className="absolute right-2.5 p-2.5 bg-[#FF4D00] disabled:opacity-50 disabled:pointer-events-none text-white rounded-full border-2 border-black shadow-[3px_3px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none transition-all"'
)

content = content.replace(
    'className="w-full bg-white border-2 border-[#121212] rounded-md py-4 pl-5 pr-16 text-[#121212] font-medium font-sans placeholder-[#121212]/50 focus:outline-none focus:translate-x-[2px] focus:translate-y-[2px] focus:shadow-[2px_2px_0px_0px_#121212] transition-all disabled:opacity-50 shadow-[4px_4px_0px_0px_#121212]"',
    'className="w-full bg-white border-2 border-black rounded-full py-4 pl-5 pr-16 text-black font-medium font-sans placeholder-gray-500 focus:outline-none focus:translate-x-[2px] focus:translate-y-[2px] focus:shadow-[2px_2px_0px_0px_#000000] transition-all disabled:opacity-50 shadow-[4px_4px_0px_0px_#000000]"'
)

content = content.replace(
    'className="text-xs font-mono font-bold bg-white hover:bg-[#121212] hover:text-white border-2 border-[#121212] px-3 py-1.5 rounded-md text-[#121212] transition-all flex items-center gap-1.5 shadow-[2px_2px_0px_0px_#121212] hover:shadow-none hover:translate-x-[2px] hover:translate-y-[2px] cursor-pointer"',
    'className="bg-[#FF4D00] text-white border-2 border-black font-mono font-bold text-xs px-2.5 py-1 rounded-full shadow-[1.5px_1.5px_0px_0px_#000000] active:translate-x-[1.5px] active:translate-y-[1.5px] active:shadow-none hover:bg-black transition-all flex items-center gap-1.5 cursor-pointer"'
)

content = content.replace('border-[#121212]', 'border-black')
content = content.replace('text-[#121212]', 'text-black')
content = content.replace('bg-[#121212]', 'bg-black')
content = content.replace('shadow-[4px_4px_0px_0px_#121212]', 'shadow-[4px_4px_0px_0px_#000000]')
content = content.replace('shadow-[3px_3px_0px_0px_#121212]', 'shadow-[3px_3px_0px_0px_#000000]')
content = content.replace('shadow-[2px_2px_0px_0px_#121212]', 'shadow-[2px_2px_0px_0px_#000000]')
content = content.replace('shadow-[1px_1px_0px_0px_#121212]', 'shadow-[1px_1px_0px_0px_#000000]')
content = content.replace('shadow-[6px_6px_0px_0px_#121212]', 'shadow-[6px_6px_0px_0px_#000000]')

with open('web/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
