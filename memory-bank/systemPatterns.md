# System Patterns

## System Architecture

The system consists of the following components:

*   **Telegram Bot:** Listens for messages containing Telegram post links.
*   **Post Downloader:** Downloads the Telegram post content from the provided link.
*   **Content Formatter:**  
  - Formats raw Telegram message data into EPUB-compatible content.
  - Handles text formatting, links, and basic structure.
  - Adds logic to extract media files from forwarded messages.
  - Saves images into the EPUB structure with support for `<img>` tags.
*   **EPUB Generator:** Generates the EPUB file from the formatted content.
*   **File Storage:** Stores the generated EPUB file.

## Key Technical Decisions

*   Using Python for its ease of use and extensive libraries.
*   Using `python-telegram-bot` for Telegram bot development.
*   Using `ebooklib` for EPUB generation.

## Design Patterns in Use

*   **Facade:** The Telegram Bot component acts as a facade, hiding the complexity of the other components from the user.
*   **Strategy:** The Content Formatter component can use different strategies for formatting the content, depending on the type of Telegram post.

## Component Relationships

The Telegram Bot component interacts with the Post Downloader, Content Formatter, EPUB Generator, and File Storage components.

## Critical Implementation Paths

1.  User sends a Telegram post link to the bot.
2.  The bot forwards the link to the Post Downloader.
3.  The Post Downloader downloads the content of the post.
4.  The Content Formatter formats the content.
5.  The EPUB Generator generates the EPUB file.
6.  The File Storage stores the EPUB file.
7.  The bot sends the EPUB file to the user.
