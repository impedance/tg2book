import os
from datetime import datetime
import re
from ebooklib import epub
import tempfile
import threading
import requests

def create_epub(title, author, content, output_path):
    # Create the EPUB book
    book = epub.EpubBook()
    book.set_identifier('id123456')
    book.set_title(title)
    book.set_language('en')
    book.add_author(author)

    # Define CSS style
    style = '''
    BODY {
        color: black;
        font-family: serif;
        margin: 5%;
    }
    p {
        margin-top: 0.5em;
        margin-bottom: 0.5em;
    }
    '''
    
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)

    # Create main content without any additional formatting
    main_content = epub.EpubHtml(title=title, file_name='content.xhtml', lang='en')
    
    # Wrap content in simple HTML without adding links or list formatting
    # Just preserve the exact content formatting
    main_content.content = f'''
    <html>
        <head>
            <title>{title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css" />
        </head>
        <body>
            {content}
        </body>
    </html>
    '''

    # Add content to the book
    book.add_item(main_content)

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Add CSS file
    book.add_item(nav_css)

    # Basic spine - только контент без отдельных глав и оглавления
    book.spine = [main_content]

    # Write to the file
    epub.write_epub(output_path, book, {})

    return output_path