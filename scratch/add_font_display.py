import re

with open('web/app/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Add font-display to headings and buttons
content = content.replace('font-extrabold', 'font-display font-extrabold')
content = content.replace('font-black', 'font-display font-black')

# Let's also make sure h1, h2, h3 in the markdown have font-display
content = content.replace('<h1 className="text-2xl font-display font-extrabold', '<h1 className="text-2xl font-display font-extrabold')
content = content.replace('<h2 className="text-xl font-bold', '<h2 className="text-xl font-display font-bold')
content = content.replace('<h3 className="text-lg font-bold', '<h3 className="text-lg font-display font-bold')

# Remove duplicate font-display if any
content = content.replace('font-display font-display', 'font-display')

with open('web/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
