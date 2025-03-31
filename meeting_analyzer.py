# meeting_analyzer.py
import re
import logging

class MeetingAnalyzer:
    """
    Analyzes text to determine meeting format and location based on a target city and/or state.
    """

    def __init__(self, target_city=None, target_state=None):
        """
        Initializes the analyzer with a target location (city and/or state).

        Args:
            target_city (str, optional): The city name to search for. Case-insensitive.
            target_state (str, optional): The state/region abbreviation or full name. Case-insensitive.
        """
        if not target_city and not target_state:
            raise ValueError("MeetingAnalyzer requires at least a target_city or target_state.")

        self.target_city = target_city
        self.target_state = target_state

        log_msg = "Analyzer initialized to search for"
        if target_city:
            log_msg += f" city: '{self.target_city}'"
        if target_state:
            log_msg += f"{' and' if target_city else ''} state/region: '{self.target_state}'"
        logging.info(log_msg)

        # --- Keep existing Base Regex Patterns ---
        # These seem generally reliable for format detection
        self.meeting_context_regex = re.compile(
            r"(?i)(?:annual|special)\s+(?:stockholder|shareholder)s?\s+meeting.*?(?:will\s+be\s+held|location|time\s+and\s+place|virtual|online|webcast|physical|in\s+person)",
            re.VERBOSE | re.DOTALL
        )
        self.virtual_only_regex = re.compile(
            r"(?i)meeting\s+will\s+be\s+held\s+(?:solely\s+online|exclusively\s+online|entirely\s+by\s+means\s+of\s+remote\s+communication|in\s+a\s+virtual(?:\s+only)?\s+format|(?:via|by)\s+(?:live\s+)?(?:webcast|audio\s+conference|internet))(?!\s+and\s+at\s+a\s+physical\s+location)",
            re.VERBOSE
        )
        self.hybrid_regex = re.compile(
            r"(?i)(?:hybrid\s+meeting|(?:held\s+both|attend)\s+(?:in\s+person\s+and\s+(?:virtually|online|remotely))|(?:held\s+(?:virtually|online|remotely)\s+and\s+(?:in\s+person|at\s+a\s+physical\s+location)))",
            re.VERBOSE
        )
        self.not_in_person_regex = re.compile(
            r"(?i)no\s+physical\s+location|not\s+be\s+able\s+to\s+attend\s+in\s+person",
            re.VERBOSE
        )

       # *** Revised Physical Location Context Regex ***
        # Aim to capture a larger block after the keywords, stopping at likely boundaries like double newlines.
        self.physical_location_context_regex = re.compile(
             r"""
             (?ix) # Case-insensitive, Verbose, DOTALL allows . to match newline

             # Keywords indicating location follows (Keep these fairly broad)
             (?:
                 will\s+be\s+held\s+at |
                 location\s*[:=] |
                 address\s*[:=] |
                 place\s*[:=] |
                 at\s+our\s+principal\s+executive\s+offices(?:,|,\s+located\s+at)? | # Handle variations
                 at\s+the\s+offices\s+of
             )
             \s* # Optional whitespace after keyword

             # Start capturing group 1: The Address Snippet
             (
                 # Capture characters (including single newlines) until a likely end-of-address signal.
                 # Stop capturing if we encounter two consecutive newlines (\n\s*\n)
                 # or reach a generous limit (e.g., 250 chars).
                 (?:[^\n] | \n(?!\s*\n) ){1,250} # Match non-newlines, or single newlines not followed by another newline, up to 250 times.

                 # This pattern tries to capture typical multi-line addresses effectively.
             )
             # End capturing group 1
             """,
             re.VERBOSE | re.DOTALL # Ensure DOTALL is active for potential multi-line capture needs if using '.'
        )

        # --- DYNAMIC Target Location Regex (Build based on input - KEEP AS IS) ---
        self.target_location_regex = self._build_target_location_regex()
        logging.debug(f"Compiled target location regex: {self.target_location_regex.pattern}")


    def _build_state_pattern(self, state_input):
        # (Keep this helper as is)
        return r'\b' + re.escape(state_input) + r'\b'

    def _build_target_location_regex(self):
        # (Keep this builder logic as is - it seemed correct)
        pattern = r""
        if self.target_city and self.target_state:
            city_pattern = r'\b' + re.escape(self.target_city) + r'\b'
            state_pattern = self._build_state_pattern(self.target_state)
            pattern = city_pattern + r'(?:[,\s]+.*?)??' + state_pattern # Allow stuff between city/state + comma/space sep
        elif self.target_city:
            pattern = r'\b' + re.escape(self.target_city) + r'\b'
        elif self.target_state:
            state_pattern = self._build_state_pattern(self.target_state)
            # Look for state potentially after comma/space, before zip/end
            pattern = r'(?:,|\s)+\s*' + state_pattern + r'(?=(\s+\d{5}|\s+|$|,))'

        if not pattern:
             logging.error("Target location regex pattern is empty!")
             return re.compile(r"a^") # Regex that never matches
        return re.compile(pattern, re.IGNORECASE)


    def analyze(self, text):
        """
        Analyzes text for meeting format and checks if physical location matches target.
        (Analysis logic flow mostly reverted to previous successful pattern, using updated regexes)
        """
        if not text or len(text) < 50:
            return {'meeting_format': 'Undetermined', 'is_in_target_location': None, 'confidence': 'Low', 'snippet': 'No text or too short.'}

        format_result = 'Undetermined'
        is_target = None
        confidence = 'Low'
        snippet = ''
        clean_text = ' '.join(text.split()) # Normalize whitespace

        # --- Analysis Logic ---

        # 1. Check Virtual Only (High Confidence) - Keep this first
        virtual_match = self.virtual_only_regex.search(clean_text)
        if virtual_match:
            context_window = clean_text[max(0, virtual_match.start()-150):virtual_match.end()+150]
            if not self.hybrid_regex.search(context_window):
                 format_result = 'Virtual'
                 confidence = 'High'
                 snippet = virtual_match.group(0)
                 logging.info("Found strong virtual indicator.")
                 return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}

        # 2. Check Hybrid (High Confidence) - Keep this second
        hybrid_match = self.hybrid_regex.search(clean_text)
        if hybrid_match:
            format_result = 'Hybrid'
            confidence = 'High' # Start high for Hybrid format
            base_snippet = hybrid_match.group(0)
            logging.info("Found hybrid indicator.")
            # Try to find the physical address component using the revised regex
            physical_match_hybrid = self.physical_location_context_regex.search(clean_text)
            if physical_match_hybrid:
                 # Group 1 should contain the address snippet
                 address_snippet_hybrid = physical_match_hybrid.group(1).strip()
                 logging.debug(f"Hybrid check found address snippet: '{address_snippet_hybrid}'")
                 # Check if this snippet matches the DYNAMIC target regex
                 if self.target_location_regex.search(address_snippet_hybrid):
                     is_target = True
                     # Confidence remains High (format & location match)
                     snippet = base_snippet + f" | Target Location Confirmed in: '{address_snippet_hybrid}'"
                     logging.info(f"Hybrid target location confirmed.")
                 else:
                     is_target = False # Hybrid, but not the target location
                     confidence = 'Medium' # Confident format, location mismatch found/suspected
                     snippet = base_snippet + f" | Non-Target Location Found/Suspected: '{address_snippet_hybrid}'"
                     logging.info(f"Hybrid location is not target.")
            else:
                 # Hybrid format known, but physical address details not found/parsed by regex
                 is_target = None # Can't confirm/deny target location
                 confidence = 'Medium' # Confident format, location unclear
                 snippet = base_snippet + " | Physical location details unclear or not parsed."
                 logging.info("Hybrid format, but physical location details not parsed.")

            return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}

        # 3. Check Explicit "Not In Person" (Medium Confidence Virtual)
        not_in_person_match = self.not_in_person_regex.search(clean_text)
        if not_in_person_match and format_result == 'Undetermined':
             format_result = 'Virtual'
             confidence = 'Medium'
             snippet = not_in_person_match.group(0)
             logging.info("Found 'not in person' indicator.")
             return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}


        # 4. Look for Physical Location Context (Potential In-Person) - USING REVISED REGEX
        physical_match = self.physical_location_context_regex.search(clean_text)
        if physical_match and format_result == 'Undetermined':
             format_result = 'In-Person' # Tentative format
             confidence = 'Medium'
             # Group 1 should contain the broader address block now
             address_snippet = physical_match.group(1).strip()
             snippet = f"Potential Address Found: '{address_snippet}'" # Initial snippet
             logging.info(f"Found potential physical location context: '{address_snippet}'") # Log the *fuller* snippet

             # 5. Check if the found location snippet matches the TARGET regex
             if self.target_location_regex.search(address_snippet): # Check within the broader snippet
                 is_target = True
                 confidence = 'High'
                 logging.info(f"Target location confirmed within address snippet.")
                 snippet = address_snippet # Make snippet the specific address block found
             else:
                 is_target = False
                 logging.info(f"Physical location found, but target ({self.target_city or ''}/{self.target_state or ''}) not found within snippet: '{address_snippet}'")
                 snippet = address_snippet # Show the non-target address block

             # 6. Refinement: Check for nearby virtual terms (potential ambiguity - KEEP THIS)
             # Check window around the *start* of the physical match context
             search_window = clean_text[max(0, physical_match.start()-250):physical_match.end()+250]
             if self.virtual_only_regex.search(search_window) or re.search(r'(?i)\b(virtual|online|webcast|remote|teleconference)\b', search_window):
                  format_result = 'Undetermined' # Revert format due to ambiguity
                  confidence = 'Low'
                  snippet = f"Ambiguous: Found physical address snippet '{address_snippet}' but also virtual terms nearby. Context: ...{search_window[100:200]}..."
                  is_target = None # Reset flag due to format ambiguity
                  logging.warning(f"Ambiguity detected: Physical address found near virtual terms. Reverting format.")
                  # Return early if ambiguity detected after physical match attempt
                  return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}


        # 7. Final Decision if still Undetermined (Keep fallback)
        if format_result == 'Undetermined':
             if re.search(r'(?i)\bheld\s+in[-\s]person\b', clean_text):
                 format_result = 'In-Person'
                 confidence = 'Low' # Low because location not parsed/confirmed
                 is_target = None
                 snippet = "Found 'in person' text, but specific location details not parsed."
             else:
                 snippet = "Could not reliably determine meeting format or location details."
                 confidence = 'Low'
                 is_target = None
             logging.info(f"Analysis complete: Format={format_result}, Confidence={confidence}")


        return {'meeting_format': format_result,
                'is_in_target_location': is_target,
                'confidence': confidence,
                'snippet': snippet[:500]} # Limit snippet length