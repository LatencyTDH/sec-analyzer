# meeting_analyzer.py
import re
import logging

class MeetingAnalyzer:
    """
    Analyzes text to determine meeting format and location based on a target city and/or state.
    Prioritizes definitive "virtual only" language over potential physical location matches.
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

        # --- Base Regex Patterns ---
        self.meeting_context_regex = re.compile(
            r"(?i)(?:annual|special)\s+(?:stockholder|shareholder)s?\s+meeting.*?(?:will\s+be\s+held|location|time\s+and\s+place|virtual|online|webcast|physical|in\s+person)",
            re.VERBOSE | re.DOTALL
        )
        # ** ENHANCED Virtual Only Regex **
        self.virtual_only_regex = re.compile(
            r"""
            (?ix) # Case-insensitive, Verbose
            # Option 1: Explicit "held [modifier] online/virtual..."
            (?: meeting | annual \s+ meeting | special \s+ meeting ) \s+ will \s+ be \s+ held \s+
            (?:
                solely \s+ online |
                exclusively \s+ online |
                entirely \s+ by \s+ means \s+ of \s+ remote \s+ communication |
                in \s+ a \s+ virtual (?:\s+only)? \s+ format |
                (?:via|by) \s+ (?:live\s+)? (?:webcast|audio\s+conference|internet)
                # Added BDX style variations
                | exclusively \s+ via \s+ (?:the\s+)? internet (?:\s+webcast)? # Allow "internet" or "internet webcast"
                | virtually
            )
            # Option 2: Phrasing like "virtual annual meeting" without explicit physical mention nearby
            | \b virtual \s+ (?:annual|special) \s+ meeting \b
            # Option 3: Phrasing like "conducted online/virtually"
            | conducted \s+ (?: solely | exclusively )? \s+ (?: online | virtually | by \s+ remote \s+ communication )
            # Option 4: Participate online only type phrasing
            | participate \s+ (?: online | virtually ) \s+ only

            # Negative lookahead: Ensure it's NOT clearly hybrid
            (?!
                .*? # Don't allow these hybrid indicators shortly after the virtual match
                (?:
                    and \s+ also \s+ at |
                    and \s+ at \s+ a \s+ physical \s+ location |
                    available \s+ to \s+ attend \s+ in \s+ person |
                    hybrid \s+ meeting |
                    in \s+ person \s+ and \s+ virtually # Simplified hybrid check
                )
            )
            """,
            re.VERBOSE
        )

        # Hybrid Regex (Keep as is for now)
        self.hybrid_regex = re.compile(
            r"(?i)(?:hybrid\s+meeting|(?:held\s+both|attend)\s+(?:in\s+person\s+and\s+(?:virtually|online|remotely))|(?:held\s+(?:virtually|online|remotely)\s+and\s+(?:in\s+person|at\s+a\s+physical\s+location)))",
            re.VERBOSE
        )
        # ** ENHANCED Not In Person Regex **
        self.not_in_person_regex = re.compile(
            r"""
            (?ix) # Case-insensitive, Verbose
            (?:
                no \s+ physical \s+ location |
                not \s+ be \s+ able \s+ to \s+ attend \s+ in \s+ person |
                will \s+ not \s+ be \s+ held \s+ at \s+ a \s+ physical \s+ location |
                will \s+ not \s+ have \s+ a \s+ physical \s+ location | # Added variation
                shareholders \s+ may \s+ not \s+ attend \s+ the \s+ meeting \s+ in \s+ person # Added variation
            )
            # Negative lookahead: Similar check to avoid hybrid confusion
            (?!
                .*?
                (?: hybrid \s+ meeting | attend \s+ in \s+ person \s+ and )
            )
            """,
            re.VERBOSE
        )

       # Physical Location Context Regex (Keep the previous refined version for now)
       # Focus on fixing virtual detection first. Refinements here are secondary.
        self.physical_location_context_regex = re.compile(
             r"""
             (?ix) # Case-insensitive, Verbose, DOTALL allows . to match newline
             # ** Slightly refined keywords to be less likely to match headers **
             (?:
                 (?: meeting \s+ | location \s+ for \s+ the \s+ meeting \s+ | held ) \s+ at | # Require proximity to meeting words
                 meeting \s+ location \s* [:=] |
                 physical \s+ location \s* [:=] | # Be more specific than just 'location'
                 place \s* [:=] \s* (?: of \s+ the \s+ meeting )? | # Optionally link place to meeting
                 at \s+ our \s+ principal \s+ executive \s+ offices(?:,|,\s+located\s+at)? | # Keep these specific ones
                 at \s+ the \s+ offices \s+ of
             )
             \s*
             ( # Start capturing group 1: The Address Snippet
                 (?:[^\n] | \n(?!\s*\n) ){1,250} # Capture multi-line until double newline or limit
             ) # End capturing group 1
             """,
             re.VERBOSE | re.DOTALL
        )

        # Dynamic Target Location Regex (Keep as is)
        self.target_location_regex = self._build_target_location_regex()
        logging.debug(f"Compiled target location regex: {self.target_location_regex.pattern}")


    def _build_state_pattern(self, state_input):
        # Ensure state abbreviation is treated as whole word, allow full state names more flexibly
        # Handle common abbreviations vs full names
        state_input = state_input.strip()
        if len(state_input) == 2: # Likely abbreviation
             # Match common formats: ", NJ", " NJ ", " NJ," " NJ." State Of NJ
             # Ensure it's not part of a larger word e.g. "NEW JERSEY" if searching for "NJ"
             return r'(?:[,\s]\s*|\b)' + re.escape(state_input.upper()) + r'\b(?![a-zA-Z])'
        else: # Likely full name
            # Match " California", ", California", " State of California"
             return r'\b' + re.escape(state_input) + r'\b'

    def _build_target_location_regex(self):
        pattern_parts = []
        city_pattern = None
        state_pattern = None

        if self.target_city:
            # Match city name, allowing for potential variations like "St." vs "Saint" indirectly via word boundaries
            city_pattern = r'\b' + re.escape(self.target_city) + r'\b'

        if self.target_state:
             state_pattern = self._build_state_pattern(self.target_state)

        # Build the combined pattern carefully
        if city_pattern and state_pattern:
            # Look for City followed by State (with flexible separators, including optional newline)
            # Allow 1-2 words OR a zip code between city and state
            pattern_parts.append(city_pattern + r'(?:[,\s]+(?:[\w.]+\s+){0,2}?|\s+)' + state_pattern)
             # Look for State followed by City (less common for addresses, but possible)
            # pattern_parts.append(state_pattern + r'(?:[,\s]+(?:[\w.]+\s+){0,2}?|\s+)' + city_pattern) # Disable - less likely address format
        elif city_pattern:
            pattern_parts.append(city_pattern)
        elif state_pattern:
            # If only state, look for the state pattern (already includes some context like preceding comma/space)
            pattern_parts.append(state_pattern)


        if not pattern_parts:
             logging.error("Target location regex pattern is empty!")
             return re.compile(r"a^") # Regex that never matches

        final_pattern = r'|'.join(pattern_parts)
        logging.debug(f"Using final target location regex: {final_pattern}")
        # Use DOTALL because address snippets might span newlines captured by physical_location_context_regex
        return re.compile(final_pattern, re.IGNORECASE | re.DOTALL)


    def analyze(self, text):
        """
        Analyzes text for meeting format. Prioritizes definitive "virtual only" or
        "not in person" indicators before searching for physical locations.
        """
        if not text or len(text) < 50:
            return {'meeting_format': 'Undetermined', 'is_in_target_location': None, 'confidence': 'Low', 'snippet': 'No text or too short.'}

        format_result = 'Undetermined'
        is_target = None # MUST remain None if determined Virtual
        confidence = 'Low'
        snippet = ''
        # More aggressive cleaning - remove potential header noise early? Cautious approach.
        # Let's first rely on regex specificity.
        # Consider removing SEC header if it consistently causes issues:
        # header_end_match = re.search(r'</SEC-HEADER>', text, re.IGNORECASE)
        # if header_end_match:
        #    text = text[header_end_match.end():]
        clean_text = ' '.join(text.split()) # Normalize whitespace

        # --- Analysis Logic ---

        # **PRIORITY 1: Check for definitive VIRTUAL ONLY / NO PHYSICAL LOCATION**
        # Use the ENHANCED regexes
        virtual_only_match = self.virtual_only_regex.search(clean_text)
        not_in_person_match = self.not_in_person_regex.search(clean_text)

        # Determine which match occurred first, if both exist (unlikely but possible)
        first_virtual_indicator_pos = float('inf')
        definitive_match = None
        definitive_match_type = None

        if virtual_only_match:
             first_virtual_indicator_pos = virtual_only_match.start()
             definitive_match = virtual_only_match
             definitive_match_type = "Virtual Only"
        if not_in_person_match and not_in_person_match.start() < first_virtual_indicator_pos:
             first_virtual_indicator_pos = not_in_person_match.start()
             definitive_match = not_in_person_match
             definitive_match_type = "Not In Person"


        if definitive_match:
            # Check context around the specific match for hybrid contradiction
            context_window_start = max(0, definitive_match.start() - 150)
            context_window_end = definitive_match.end() + 150
            context_window = clean_text[context_window_start:context_window_end]

            if not self.hybrid_regex.search(context_window):
                log_msg_detail = definitive_match.group(0).replace('\n', ' ').strip()[:150] # Clean snippet for logging
                logging.info(f"Definitive '{definitive_match_type}' indicator found: '{log_msg_detail}...'. Setting format to Virtual.")
                return {
                    'meeting_format': 'Virtual',
                    'is_in_target_location': None, # Explicitly None
                    'confidence': 'High', # High confidence it's NOT physical
                    'snippet': definitive_match.group(0)[:500]
                }
            else:
                 log_msg_detail = definitive_match.group(0).replace('\n', ' ').strip()[:100]
                 logging.warning(f"Found '{definitive_match_type}' indicator ('{log_msg_detail}...') near hybrid language - potential ambiguity. Context: '{context_window}'")
                 # Let hybrid check handle it below.

        # PRIORITY 2: Check for HYBRID meetings (these DO have a physical component)
        hybrid_match = self.hybrid_regex.search(clean_text)
        if hybrid_match:
            format_result = 'Hybrid'
            confidence = 'High' # High confidence on format
            base_snippet = hybrid_match.group(0)
            logging.info("Found hybrid indicator.")
            is_target = None # Reset before checking physical part
            snippet = base_snippet # Start snippet

            # Now try to find the physical address component for the hybrid meeting
            search_radius = 500 # Characters before/after hybrid mention to look for address
            search_area = clean_text[max(0, hybrid_match.start() - search_radius):hybrid_match.end() + search_radius]
            # Use the slightly refined physical location regex
            physical_match_hybrid = self.physical_location_context_regex.search(search_area)

            if not physical_match_hybrid:
                physical_match_hybrid = self.physical_location_context_regex.search(clean_text) # Fallback search

            if physical_match_hybrid:
                 # Check if this physical match looks like a header first
                 address_snippet_hybrid_check = physical_match_hybrid.group(1).strip()
                 if "BUSINESS PHONE:" in address_snippet_hybrid_check or "MAIL ADDRESS:" in address_snippet_hybrid_check or "<SEC-HEADER>" in address_snippet_hybrid_check or "FILENAME>" in address_snippet_hybrid_check:
                    logging.warning(f"Hybrid check found physical location text, but it looks like header info: '{address_snippet_hybrid_check[:150]}...'. Disregarding.")
                    is_target = None # Cannot determine location from header
                    confidence = 'Medium' # Downgrade confidence as location is unclear
                    snippet += " | Physical location details unclear or likely header info."
                 else:
                    # Looks like a real address snippet
                    address_snippet_hybrid = address_snippet_hybrid_check
                    logging.debug(f"Hybrid check found address snippet: '{address_snippet_hybrid}'")
                    if self.target_location_regex.search(address_snippet_hybrid):
                        is_target = True
                        snippet += f" | Target Location Confirmed in: '{address_snippet_hybrid}'"
                        logging.info(f"Hybrid target location confirmed.")
                    else:
                        is_target = False
                        snippet += f" | Non-Target Location Found/Suspected: '{address_snippet_hybrid}'"
                        logging.info(f"Hybrid location is not target.")
            else:
                 # No physical location snippet found at all for hybrid
                 is_target = None
                 confidence = 'Medium'
                 snippet += " | Physical location details unclear or not parsed."
                 logging.info("Hybrid format, but physical location details not parsed.")

            return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}


        # PRIORITY 3: Look for IN-PERSON meetings (only if not Virtual/Hybrid)
        # Use the slightly refined physical location regex
        # Search the entire text now
        physical_match = self.physical_location_context_regex.search(clean_text)
        found_plausible_physical_location = False # Flag to track if we find a non-header match

        # Iterate through all potential matches as the first might be a header
        for match in self.physical_location_context_regex.finditer(clean_text):
             address_snippet = match.group(1).strip()
             # ** Check if the matched snippet looks like a header **
             if "BUSINESS PHONE:" in address_snippet or "MAIL ADDRESS:" in address_snippet or "<SEC-HEADER>" in address_snippet or "FILENAME>" in address_snippet:
                  logging.debug(f"Physical location regex matched potential header info: '{address_snippet[:150]}...'. Skipping this match.")
                  continue # Skip this match, look for the next one

             # If we reach here, the snippet seems like a plausible address
             found_plausible_physical_location = True
             format_result = 'In-Person'
             confidence = 'Medium' # Start Medium, upgrade if target location matches
             snippet = f"Potential Address Found: '{address_snippet}'"
             logging.info(f"Found potential physical location context: '{address_snippet}'")

             # Check if the found location snippet matches the TARGET regex
             if self.target_location_regex.search(address_snippet):
                 is_target = True
                 confidence = 'High' # High confidence: Format likely physical, target matches
                 logging.info(f"Target location confirmed within address snippet.")
                 snippet = address_snippet # Make snippet the specific address block found
             else:
                 is_target = False # Physical location found, but not the target one
                 log_target_info = f"{self.target_city or ''}/{self.target_state or ''}".strip('/')
                 logging.info(f"Physical location found, but target ({log_target_info}) not found within snippet: '{address_snippet}'")
                 snippet = address_snippet # Show the non-target address block

             # Refinement: Check for nearby virtual terms causing ambiguity
             search_window_start = max(0, match.start() - 250)
             search_window_end = match.end() + 250
             search_window = clean_text[search_window_start:search_window_end]
             if self.virtual_only_regex.search(search_window) or self.not_in_person_regex.search(search_window):
                  format_result = 'Undetermined' # Revert format due to ambiguity
                  confidence = 'Low'
                  snippet = f"Ambiguous: Found physical address snippet '{address_snippet}' but also virtual/non-physical terms nearby. Context: ...{search_window[max(0,match.start()-search_window_start-50):match.start()-search_window_start+150]}..."
                  is_target = None # Reset flag due to format ambiguity
                  logging.warning(f"Ambiguity detected: Physical address found near virtual/non-physical terms. Reverting format.")
                  # Return early due to ambiguity - we won't check further physical matches
                  return {'meeting_format': format_result, 'is_in_target_location': is_target, 'confidence': confidence, 'snippet': snippet[:500]}

             # If no ambiguity, this is our best guess for In-Person. Stop searching.
             return {'meeting_format': format_result,
                     'is_in_target_location': is_target,
                     'confidence': confidence,
                     'snippet': snippet[:500]}

        # If the loop finishes without finding a plausible physical location (found_plausible_physical_location is False)
        # or if physical_match was None initially, proceed to fallback.

        # PRIORITY 4: Fallback / Final Decision if still Undetermined
        if format_result == 'Undetermined':
             # Look for weaker 'in person' text, but location remains unknown
             if re.search(r'(?i)\bheld\s+in[-\s]person\b', clean_text):
                 format_result = 'In-Person'
                 confidence = 'Low' # Low because location not parsed/confirmed
                 is_target = None
                 snippet = "Found 'in person' text, but specific location details not parsed."
             # Check for weaker 'virtual' or 'webcast' terms if nothing else fit
             elif re.search(r'(?i)\b(virtual|webcast|online\s+meeting|remote\s+communication)\b', clean_text):
                 format_result = 'Virtual' # Could be virtual, but wasn't definitive enough for earlier checks
                 confidence = 'Low'
                 is_target = None
                 snippet = "Found general virtual/webcast terms, but not definitive 'virtual only' phrasing."
             else:
                 # Truly undetermined
                 snippet = "Could not reliably determine meeting format or location details based on keywords."
                 confidence = 'Low'
                 is_target = None # Ensure it's None

             logging.info(f"Fallback Analysis complete: Format={format_result}, Confidence={confidence}")


        # Final return dictionary (should capture results from fallbacks)
        return {'meeting_format': format_result,
                'is_in_target_location': is_target, # Crucially ensuring this is None if format is Virtual
                'confidence': confidence,
                'snippet': snippet[:500]} # Limit snippet length