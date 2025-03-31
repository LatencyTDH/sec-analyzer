import re
import logging

class MeetingAnalyzer:
    """Analyzes text to determine meeting format and location based on a target city."""

    def __init__(self, target_city, target_state=None):
        """
        Initializes the analyzer with a target location.

        Args:
            target_city (str): The city name to search for. Case-insensitive.
            target_state (str, optional): The state/region abbreviation or full name. 
                                           Helps disambiguate city names. Case-insensitive. Defaults to None.
        """
        if not target_city:
            raise ValueError("Target city must be provided.")
            
        self.target_city = target_city
        self.target_state = target_state
        logging.info(f"Analyzer initialized to search for city: '{self.target_city}'" + (f", state/region: '{self.target_state}'" if self.target_state else ""))

        # --- REGEX PATTERNS ---
        # (Keep the existing meeting_context, virtual_only, hybrid, not_in_person regex as they are)
        self.meeting_context_regex = re.compile(
            r"""
            (?i)                                # Case-insensitive mode
            (?:annual|special)\s+(?:stockholder|shareholder)s?\s+meeting # "annual/special stockholder/shareholder meeting"
            .*?                                 # Allow some text in between
            (?:will\s+be\s+held|location|time\s+and\s+place|virtual|online|webcast|physical|in\s+person) # Keywords indicating details
            """,
            re.VERBOSE | re.DOTALL 
        )
        self.virtual_only_regex = re.compile(
            r"""
            (?i)                                # Case-insensitive
            meeting\s+will\s+be\s+held\s+
            (?:
                solely\s+online |               # "solely online"
                exclusively\s+online |          # "exclusively online"
                entirely\s+by\s+means\s+of\s+remote\s+communication | # "entirely by means of..."
                in\s+a\s+virtual(?:\s+only)?\s+format | # "in a virtual format" or "virtual only format"
                (?:via|by)\s+(?:live\s+)?(?:webcast|audio\s+conference|internet) # "via live webcast/audio conference/internet"
            )
            (?!\s+and\s+at\s+a\s+physical\s+location) # Negative lookahead: ensure it doesn't mention physical *as well*
            """,
            re.VERBOSE
        )
        self.hybrid_regex = re.compile(
            r"""
            (?i)                                # Case-insensitive
            (?:
                hybrid\s+meeting |             # Explicit "hybrid meeting"
                (?:held\s+both|attend)\s+(?:in\s+person\s+and\s+(?:virtually|online|remotely)) | # "held both in person and virtually"
                (?:held\s+(?:virtually|online|remotely)\s+and\s+(?:in\s+person|at\s+a\s+physical\s+location)) # Reverse order
            )
            """,
            re.VERBOSE
        )
        self.not_in_person_regex = re.compile(
            r"""
            (?i)
            no\s+physical\s+location |      # "no physical location"
            not\s+be\s+able\s+to\s+attend\s+in\s+person # "not be able to attend in person"
            """,
            re.VERBOSE
        )

        # ** Physical Location Context Regex (Finds potential addresses near meeting keywords) **
        # Keep this relatively general to capture the address snippet first
        self.physical_location_context_regex = re.compile(
             r"""
             (?i)                                # Case-insensitive
             (?:annual|special)\s+meeting\s+(?:of\s+)?(?:stockholder|shareholder)s? # Meeting phrase
             .*?                                 # Any characters (non-greedy)
             (?:will\s+be\s+held\s+at|location:|address:|place:) # Keywords indicating location follows
             \s*                                 # Optional whitespace
             (                                   # Start capturing group for the address snippet
                 (?:                             # Address lines (repeatable)
                    (?:                             # Optional Street Address part
                       (?:No\.|Number|\#)?\s*\d+\s+[A-Z0-9].*? # Number + Street Name (simplified)
                       (?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Plaza|Place|Way|Court|Ct|Terrace)[\.,]? # Common street types
                    )?
                    .*?                             # Allow other text like building names, suites etc.
                 ){1,3}                          # Match 1-3 lines/segments loosely
                 (?:[A-Z][a-zA-Z\s]+?Building|[A-Z][a-zA-Z\s]+?Center|[A-Z][a-zA-Z\s]+?Plaza|Hotel\s+[A-Z][a-zA-Z]+)? # Optional Building/Hotel Name
                 .*?                             # Allow chars between parts
                 \b(?:[A-Z][a-zA-Z\-]+\s?){1,4}\b # Potential City Name (1-4 capitalized words)
                 (?:,|\s)+                        # Separator
                 [A-Z]{2}\b                      # State Abbreviation (usually present)
                 (?:\s+\d{5}(?:-\d{4})?)?        # Optional ZIP code
             )                                   # End capturing group
             """,
             re.VERBOSE | re.DOTALL
         )


        # ** DYNAMIC Target Location Regex (applied to snippets found above) **
        # Builds a regex to find the specific target city and optional state
        city_pattern = r'\b' + re.escape(self.target_city) + r'\b'
        state_pattern = ''
        if self.target_state:
            # Handle common variations like abbreviation vs full name if needed
            # For simplicity, just escape and use OR if state looks like an abbreviation vs longer name
            escaped_state = re.escape(self.target_state)
            if len(self.target_state) == 2 and self.target_state.isalpha(): # Likely abbreviation
                 state_pattern = r'(?:,|\s)+\s*' + escaped_state + r'\b' # Match abbreviation after comma/space
                 # Optional: Add common full name if possible (complex mapping needed)
            else: # Likely full state name
                 state_pattern = r'(?:,|\s)+\s*' + escaped_state + r'\b'
                 # Optional: Add abbreviation if possible (complex mapping needed)
            # Combine city and state pattern - look for city THEN state within reasonable distance
            # Allow city, state OR city \s+ state
            combined_pattern = city_pattern + r'(?:,|\s)*?' + state_pattern # Non-greedy match between city and state
        else:
            combined_pattern = city_pattern # Just look for the city name

        # Compile the final dynamic regex, case-insensitive
        self.target_location_regex = re.compile(combined_pattern, re.IGNORECASE)
        logging.debug(f"Compiled target location regex: {self.target_location_regex.pattern}")


    def analyze(self, text):
        """
        Analyzes the text to determine meeting format and target city location.

        Args:
            text (str): The text content of the filing.

        Returns:
            dict: A dictionary containing analysis results:
                  {'meeting_format': str, 'is_in_target_city': bool | None, 'confidence': str, 'snippet': str}
                  meeting_format: 'In-Person', 'Virtual', 'Hybrid', 'Undetermined'
                  is_in_target_city: True, False, or None (if not in-person or undetermined)
                  confidence: 'High', 'Medium', 'Low'
                  snippet: Relevant text snippet supporting the conclusion.
        """
        if not text or len(text) < 100:
            return {'meeting_format': 'Undetermined', 'is_in_target_city': None, 'confidence': 'Low', 'snippet': 'No text provided or too short.'}

        format_result = 'Undetermined'
        is_target = None
        confidence = 'Low'
        snippet = ''
        clean_text = ' '.join(text.split()) # Normalize whitespace

        # --- Analysis Logic (mostly unchanged except for location check) ---

        # 1. Check for Virtual Only
        virtual_match = self.virtual_only_regex.search(clean_text)
        if virtual_match:
            hybrid_nearby = self.hybrid_regex.search(clean_text[max(0, virtual_match.start()-200):virtual_match.end()+200])
            if not hybrid_nearby:
                 format_result = 'Virtual'
                 confidence = 'High'
                 snippet = virtual_match.group(0)
                 logging.info("Found strong virtual indicator.")
                 return {'meeting_format': format_result, 'is_in_target_city': None, 'confidence': confidence, 'snippet': snippet[:500]}

        # 2. Check for Hybrid
        hybrid_match = self.hybrid_regex.search(clean_text)
        if hybrid_match:
            format_result = 'Hybrid'
            confidence = 'High'
            snippet = hybrid_match.group(0)
            logging.info("Found hybrid indicator.")
            # Check for target city physical location component if hybrid
            physical_match_hybrid = self.physical_location_context_regex.search(clean_text)
            if physical_match_hybrid:
                 address_snippet_hybrid = physical_match_hybrid.group(1) # Captured address part
                 # Use the DYNAMIC regex here
                 if self.target_location_regex.search(address_snippet_hybrid):
                     is_target = True
                     snippet += f" | Target Location ({self.target_city}) Confirmed: " + address_snippet_hybrid
                 else:
                     is_target = False
                     snippet += " | Non-Target Location Found: " + address_snippet_hybrid
            else:
                 is_target = None # Physical location mentioned but details not matched/found
                 snippet += " | Physical location details unclear."

            return {'meeting_format': format_result, 'is_in_target_city': is_target, 'confidence': confidence, 'snippet': snippet[:500]}

        # 3. Check for explicit "not in person"
        not_in_person_match = self.not_in_person_regex.search(clean_text)
        if not_in_person_match and format_result == 'Undetermined':
             format_result = 'Virtual'
             confidence = 'Medium'
             snippet = not_in_person_match.group(0)
             logging.info("Found 'not in person' indicator.")
             return {'meeting_format': format_result, 'is_in_target_city': None, 'confidence': confidence, 'snippet': snippet[:500]}


        # 4. Look for Physical Location Context (if not already determined)
        physical_match = self.physical_location_context_regex.search(clean_text)
        if physical_match and format_result == 'Undetermined':
             format_result = 'In-Person'
             confidence = 'Medium'
             address_snippet = physical_match.group(1)
             snippet = physical_match.group(0) # Initial snippet is the broader context
             logging.info(f"Found potential physical location context: {address_snippet}")

             # 5. Check if the found location is the TARGET city/state
             # Use the DYNAMIC regex here
             if self.target_location_regex.search(address_snippet):
                 is_target = True
                 confidence = 'High' # More confident if target match is clear within address
                 logging.info(f"Target location ({self.target_city}) confirmed within address snippet.")
                 snippet = address_snippet # Make snippet more specific
             else:
                 is_target = False
                 logging.info(f"Physical location found, but does not appear to be target ({self.target_city}). Snippet: {address_snippet}")
                 snippet = address_snippet # Show the non-target address

             # Refinement: Check again for virtual keywords *near* this physical match
             search_window = clean_text[max(0, physical_match.start()-300):physical_match.end()+300]
             if self.virtual_only_regex.search(search_window) or re.search(r'(?i)\b(?:virtual|online|webcast|remote)\b', search_window):
                  format_result = 'Undetermined' # Revert due to ambiguity
                  confidence = 'Low'
                  snippet = f"Ambiguous: Found physical address '{address_snippet}' but also virtual terms nearby: {search_window[max(0, physical_match.start()-300 - (max(0, physical_match.start()-300))):100]}..." # Show context
                  is_target = None # Reset flag due to ambiguity
                  logging.warning(f"Ambiguity detected: Physical address found near virtual terms. Snippet: {snippet}")


        # 6. Final Decision
        if format_result == 'Undetermined':
             snippet = "Could not reliably determine meeting format or location from text."
             logging.info("Analysis complete: Format Undetermined.")


        return {'meeting_format': format_result, 'is_in_target_city': is_target, 'confidence': confidence, 'snippet': snippet[:500]}