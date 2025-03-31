from bs4 import BeautifulSoup
import logging
import re

class TextParser:
    """Parses text content from filing files (HTML or TXT)."""

    @staticmethod
    def extract_text_from_file(file_path):
        """
        Extracts relevant text content from a given filing file.
        Handles both HTML and TXT files.

        Args:
            file_path (str): Path to the filing file.

        Returns:
            str: Extracted and cleaned text content, or None if error.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if file_path.lower().endswith(('.htm', '.html')):
                # Parse HTML
                soup = BeautifulSoup(content, 'lxml') # Use lxml for speed

                # Remove script and style elements
                for script_or_style in soup(["script", "style"]):
                    script_or_style.decompose()

                # Get text, normalize whitespace
                text = soup.get_text(separator=' ', strip=True)

            elif file_path.lower().endswith('.txt'):
                 # Basic TXT handling - might need more sophisticated cleaning
                 # Check if it looks like HTML within the TXT
                if '<html' in content[:1000].lower() or '<body' in content[:1000].lower():
                     soup = BeautifulSoup(content, 'lxml')
                     for script_or_style in soup(["script", "style"]):
                         script_or_style.decompose()
                     text = soup.get_text(separator=' ', strip=True)
                else:
                    # Assume plain text if no strong HTML indicators
                    text = content
            else:
                 logging.warning(f"Unsupported file type: {file_path}")
                 return None

            # General text cleaning (apply to both HTML and TXT derived text)
            text = ' '.join(text.split()) # Normalize whitespace
            text = text.replace('\xa0', ' ') # Replace non-breaking spaces
            
            # Optional: More aggressive cleaning (e.g., removing excessive line breaks if needed)
            # text = re.sub(r'\n\s*\n', '\n', text) # Remove multiple blank lines

            logging.debug(f"Successfully extracted text from: {file_path}")
            return text

        except FileNotFoundError:
            logging.error(f"File not found: {file_path}")
            return None
        except Exception as e:
            logging.error(f"Error parsing file {file_path}: {e}")
            return None