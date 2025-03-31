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
        self.physical_location_context_regex = re.compile(
             r"""
             (?i) # Case-insensitive
             (?:annual|special)\s+meeting\s+(?:of\s+)?(?:stockholder|shareholder)s? # Meeting phrase
             .*? # Non-greedy match
             (?:will\s+be\s+held\s+at|location:|address:|place:) # Location keywords
             \s*
             ( # Start capturing group for address snippet
                 (?: # Optional Street Address line(s)
                    (?:(?:No\.|Number|\#)?\s*\d+\s+[A-Z0-9].*?)? # Number + Street Name (simplified)
                    (?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Plaza|Place|Way|Court|Ct|Terrace|Center|Centre)[\.,]? # Common types
                    .*? # Allow other text like building names, suites etc. between parts
                 ){1,4} # Match 1-4 address segments/lines loosely
                 (?:[A-Z][a-zA-Z\s\-]+?Building|[A-Z][a-zA-Z\s\-]+?Center|[A-Z][a-zA-Z\s\-]+?Plaza|Hotel\s+[A-Z][a-zA-Z\-]+)? # Optional Building/Hotel
                 .*?
                 \b(?:[A-Z][a-zA-Z\-]+\s?){1,4}\b # Potential City Name
                 (?:,|\s)+ # Separator
                 (?:[A-Z]{2}|[A-Za-z]{3,})\b # State Abbreviation or maybe full name
                 (?:\s+\d{5}(?:-\d{4})?)? # Optional ZIP
             ) # End capturing group
             """,
             re.VERBOSE | re.DOTALL
         )

        # --- ** DYNAMIC Target Location Regex (Build based on input) ** ---
        self.target_location_regex = self._build_target_location_regex()
        logging.debug(f"Compiled target location regex: {self.target_location_regex.pattern}")


    def _build_state_pattern(self, state_input):
        """Helper to create a pattern for a state (escaped, word boundaries)."""
        # Basic: escape and add word boundaries
        # Improvement: Handle common variations (e.g., "NY" vs "New York") if a mapping is available
        # For now, just match the input string exactly (case-insensitive later)
        return r'\b' + re.escape(state_input) + r'\b'

    def _build_target_location_regex(self):
        """Builds the regex used to match the target location within an address snippet."""
        pattern = r""
        if self.target_city and self.target_state:
            # City AND State: Look for city, then state nearby
            city_pattern = r'\b' + re.escape(self.target_city) + r'\b'
            state_pattern = self._build_state_pattern(self.target_state)
            # Pattern: City, optional comma/space (non-greedy), State Boundary
            pattern = city_pattern + r'(?:,|\s)*?' + state_pattern
        elif self.target_city:
            # City ONLY: Look for the city name
            pattern = r'\b' + re.escape(self.target_city) + r'\b'
        elif self.target_state:
            # State ONLY: Look for the state name/abbr after a likely separator
            state_pattern = self._build_state_pattern(self.target_state)
            # Pattern: Comma or space(s), then the State Pattern, followed by zip/space/end
            # This assumes the state appears *after* a city or similar element in the address snippet
            pattern = r'(?:,|\s)+\s*' + state_pattern + r'(?=(\s+\d{5}|\s+|$))' # Lookahead for zip/space/end
            # Alternative State Only (simpler, relies more on address context regex):
            # pattern = self._build_state_pattern(self.target_state)

        if not pattern:
             # Should not happen due to __init__ check, but safeguard
             logging.error("Target location regex pattern is empty!")
             return re.compile(r"a^") # Regex that never matches

        # Compile the final dynamic regex, case-insensitive
        return re.compile(pattern, re.IGNORECASE)


    def analyze(self, text):
        """
        Analyzes text for meeting format and checks if physical location matches target.

        Returns:
            dict: {'meeting_format': str, 'is_in_target_location': bool | None, ...}
                  is_in_target_location: True if format is In-Person/Hybrid and location matches,
                                         False if format is In-Person/Hybrid and location doesn't match,
                                         None otherwise (Virtual, Undetermined, Parse Error, or physical address not found).
        """
        if not text or len(text) < 50: # Adjusted length slightly
            return {'meeting_format': 'Undetermined', 'is_in_target_location': None, 'confidence': 'Low', 'snippet': 'No text or too short.'}

        format_result = 'Undetermined'
        is_target = None # Default to None
        confidence = 'Low'
        snippet = ''
        clean_text = ' '.join(text.split()) # Normalize whitespace

        # --- Analysis Logic ---

        # 1. Check Virtual Only (High Confidence)
        virtual_match = self.virtual_only_regex.search(clean_text)
        if virtual_match:
            # Check context for hybrid keywords to reduce false positives
            context_window = clean_text[max(0, virtual_match.start()-150):virtual_match.end()+150]
            if not self.hybrid_regex.search(context_window):
                 format_result = 'Virtual'
                 confidence = 'High'
                 snippet = virtual_match.group(0)
                 logging.info("Found strong virtual indicator.")
                 # is_target remains None for Virtual
                 return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}

        # 2. Check Hybrid (High Confidence)
        hybrid_match = self.hybrid_regex.search(clean_text)
        if hybrid_match:
            format_result = 'Hybrid'
            confidence = 'High'
            snippet = hybrid_match.group(0)
            logging.info("Found hybrid indicator.")
            # Try to find the physical address component for location check
            physical_match_hybrid = self.physical_location_context_regex.search(clean_text)
            if physical_match_hybrid:
                 address_snippet_hybrid = physical_match_hybrid.group(1).strip()
                 # Check if the extracted address snippet matches the target location regex
                 if self.target_location_regex.search(address_snippet_hybrid):
                     is_target = True
                     confidence = 'High' # Confident about format and location match
                     snippet += f" | Target Location Confirmed in: '{address_snippet_hybrid}'"
                 else:
                     is_target = False # Hybrid, but not the target location
                     confidence = 'Medium' # Confident about format, location mismatch found
                     snippet += f" | Non-Target Location Found: '{address_snippet_hybrid}'"
            else:
                 # Hybrid format known, but physical address details not found/parsed
                 is_target = None # Can't confirm/deny target location
                 confidence = 'Medium' # Confident about format, location unclear
                 snippet += " | Physical location details unclear."

            return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}

        # 3. Check Explicit "Not In Person" (Medium Confidence Virtual)
        not_in_person_match = self.not_in_person_regex.search(clean_text)
        # Only apply if format is still undetermined (avoid overriding Hybrid)
        if not_in_person_match and format_result == 'Undetermined':
             format_result = 'Virtual'
             confidence = 'Medium'
             snippet = not_in_person_match.group(0)
             logging.info("Found 'not in person' indicator.")
             # is_target remains None for Virtual
             return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}

        # 4. Look for Physical Location Context (Potential In-Person, Medium Confidence)
        physical_match = self.physical_location_context_regex.search(clean_text)
        if physical_match and format_result == 'Undetermined':
             format_result = 'In-Person' # Tentative format
             confidence = 'Medium' # Initially medium, raised if location matches
             address_snippet = physical_match.group(1).strip()
             snippet = f"Potential Address Found: '{address_snippet}'" # Start snippet
             logging.info(f"Found potential physical location context: {address_snippet}")

             # 5. Check if the found location snippet matches the TARGET regex
             if self.target_location_regex.search(address_snippet):
                 is_target = True
                 confidence = 'High' # Upgrade confidence: In-Person format likely & location matches
                 logging.info(f"Target location confirmed within address snippet: {address_snippet}")
                 snippet = address_snippet # Make snippet the address itself
             else:
                 is_target = False
                 logging.info(f"Physical location found, but not the target. Snippet: {address_snippet}")
                 snippet = address_snippet # Show the non-target address

             # 6. Refinement: Check for nearby virtual terms (potential ambiguity)
             search_window = clean_text[max(0, physical_match.start()-250):physical_match.end()+250]
             # Look for virtual-only patterns or common virtual keywords nearby
             if self.virtual_only_regex.search(search_window) or re.search(r'(?i)\b(virtual|online|webcast|remote|teleconference)\b', search_window):
                  # If strong virtual signals nearby, downgrade confidence, format -> Undetermined
                  # Avoid doing this if we already found explicit Hybrid marker before
                  format_result = 'Undetermined'
                  confidence = 'Low'
                  snippet = f"Ambiguous: Physical address '{address_snippet}' found near virtual terms like '{search_window[100:200]}...'" # Show context
                  is_target = None # Reset flag due to format ambiguity
                  logging.warning(f"Ambiguity detected: Physical address found near virtual terms. Reverting format to Undetermined.")

        # 7. Final Decision if still Undetermined
        if format_result == 'Undetermined':
             # Could try a broader search for 'in person' if nothing else found
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