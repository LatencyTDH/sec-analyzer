import re
import logging

class MeetingAnalyzer:
    """Analyzes text to determine meeting format and location."""

    def __init__(self):
        # --- REGEX PATTERNS ---
        # More robust patterns focusing on context

        # ** Meeting Context Keywords **
        # Look for sections/sentences discussing the annual meeting details
        # Using broader context around keywords like "annual meeting", "shareholder meeting"
        # (?i) for case-insensitive search
        self.meeting_context_regex = re.compile(
            r"""
            (?i)                                # Case-insensitive mode
            (?:annual|special)\s+(?:stockholder|shareholder)s?\s+meeting # "annual/special stockholder/shareholder meeting"
            .*?                                 # Allow some text in between
            (?:will\s+be\s+held|location|time\s+and\s+place|virtual|online|webcast|physical|in\s+person) # Keywords indicating details
            """,
            re.VERBOSE | re.DOTALL # Verbose allows comments, DOTALL makes '.' match newlines
        )

        # ** Virtual Meeting Indicators (Strong evidence) **
        # Prioritize explicit statements of virtual-only
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

        # ** Hybrid Meeting Indicators **
        # Look for mentions of both physical and virtual participation
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

         # ** In-Person Indicators (Look for physical address context) **
         # This is often implicit - presence of an address without strong virtual cues
         # We look for address patterns *near* meeting context words.
         # Use a wider search window initially.
        self.physical_location_context_regex = re.compile(
            r"""
            (?i)                                # Case-insensitive
            (?:annual|special)\s+meeting\s+(?:of\s+)?(?:stockholder|shareholder)s? # Meeting phrase
            .*?                                 # Any characters (non-greedy)
            (?:will\s+be\s+held\s+at|location:|address:|place:) # Keywords indicating location follows
            \s*                                 # Optional whitespace
            (                                   # Start capturing group for the address snippet
                (?:                               # Non-capturing group for address components
                    (?:No\.|Number|\#)?\s*\d+\s+[A-Z][a-zA-Z\s,]+? # Street number and name (simple version)
                    (?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Plaza|Suite|Floor)[\.,]? # Street type
                    \s*
                )?                                # Make street address optional (might just be building name)
                (?:[A-Z][a-zA-Z\s]+?Building|[A-Z][a-zA-Z\s]+?Center|[A-Z][a-zA-Z\s]+?Plaza)? # Building Name
                .*?                               # Allow some chars between parts
                (?:New\s+York|NYC|Manhattan|Brooklyn|Queens|Bronx|Staten\s+Island) # NYC Boroughs/Names
                (?:,|\s)+N(?:ew\s*)?Y(?:ork)?\.? # State (NY, New York) - optional period
                (?:\s+\d{5}(?:-\d{4})?)?        # Optional ZIP code
            )                                   # End capturing group
            """,
            re.VERBOSE | re.DOTALL
        )
        
        # ** Specific NYC Location Regex (applied to snippets found above) **
        # More precise check for NYC variations within a confirmed physical address context
        self.nyc_regex = re.compile(
            r"""
            (?i)                          # Case-insensitive
            \b(?:                         # Word boundary, start non-capturing group
                New\s+York\s*,\s*N(?:ew\s*)?Y(?:ork)? | # New York, NY / New York, New York
                NYC |                     # NYC
                Manhattan |               # Manhattan
                Brooklyn |                # Brooklyn
                Queens |                  # Queens
                Bronx |                   # The Bronx / Bronx
                Staten\s+Island          # Staten Island
            )\b                          # Word boundary
            """,
            re.VERBOSE
        )
        
        # ** Negative cues for In-Person (Helps rule out false positives) **
        self.not_in_person_regex = re.compile(
            r"""
            (?i)
            no\s+physical\s+location |      # "no physical location"
            not\s+be\s+able\s+to\s+attend\s+in\s+person # "not be able to attend in person"
            """,
            re.VERBOSE
        )


    def analyze(self, text):
        """
        Analyzes the text to determine meeting format and NYC location.

        Args:
            text (str): The text content of the filing.

        Returns:
            dict: A dictionary containing analysis results:
                  {'meeting_format': str, 'is_in_nyc': bool | None, 'confidence': str, 'snippet': str}
                  meeting_format: 'In-Person', 'Virtual', 'Hybrid', 'Undetermined'
                  is_in_nyc: True, False, or None (if not in-person or undetermined)
                  confidence: 'High', 'Medium', 'Low'
                  snippet: Relevant text snippet supporting the conclusion.
        """
        if not text or len(text) < 100: # Basic check for valid text
            return {'meeting_format': 'Undetermined', 'is_in_nyc': None, 'confidence': 'Low', 'snippet': 'No text provided or too short.'}

        # --- Analysis Strategy ---
        # 1. Look for explicit virtual-only statements.
        # 2. Look for explicit hybrid statements.
        # 3. Look for explicit "not in person" statements.
        # 4. Look for physical address details near meeting context.
        # 5. If physical address found, check if it's NYC.
        # 6. If none of the above, classify as Undetermined.

        format_result = 'Undetermined'
        is_nyc = None
        confidence = 'Low'
        snippet = ''

        # Search within a reasonable window around meeting keywords first for efficiency
        # Combine results from targeted and full searches if needed
        # For simplicity here, we search the whole text but prioritize regex logic
        
        # Clean text slightly for regex robustness
        clean_text = ' '.join(text.split()) # Normalize whitespace

        # 1. Check for Virtual Only
        virtual_match = self.virtual_only_regex.search(clean_text)
        if virtual_match:
            # Double check against hybrid keywords nearby - refine if needed
            hybrid_nearby = self.hybrid_regex.search(clean_text[max(0, virtual_match.start()-200):virtual_match.end()+200])
            if not hybrid_nearby: # If no hybrid terms nearby, likely virtual
                 format_result = 'Virtual'
                 confidence = 'High'
                 snippet = virtual_match.group(0)
                 logging.info("Found strong virtual indicator.")
                 return {'meeting_format': format_result, 'is_in_nyc': None, 'confidence': confidence, 'snippet': snippet[:500]} # Limit snippet length

        # 2. Check for Hybrid
        hybrid_match = self.hybrid_regex.search(clean_text)
        if hybrid_match:
            format_result = 'Hybrid'
            confidence = 'High'
            snippet = hybrid_match.group(0)
            logging.info("Found hybrid indicator.")
             # Check for NYC physical location component if hybrid
            physical_match_hybrid = self.physical_location_context_regex.search(clean_text)
            if physical_match_hybrid:
                 address_snippet_hybrid = physical_match_hybrid.group(1) # Captured address part
                 if self.nyc_regex.search(address_snippet_hybrid):
                     is_nyc = True
                     snippet += " | NYC Location Confirmed: " + address_snippet_hybrid
                 else:
                     is_nyc = False
                     snippet += " | Non-NYC Location Found: " + address_snippet_hybrid
            else:
                 is_nyc = None # Physical location mentioned but details not matched/found
                 snippet += " | Physical location details unclear."

            return {'meeting_format': format_result, 'is_in_nyc': is_nyc, 'confidence': confidence, 'snippet': snippet[:500]}

        # 3. Check for explicit "not in person"
        not_in_person_match = self.not_in_person_regex.search(clean_text)
        if not_in_person_match and format_result == 'Undetermined': # Avoid overriding Hybrid
             # This often implies virtual, but let's be cautious
             format_result = 'Virtual' # Reclassify as Virtual if explicitly not physical
             confidence = 'Medium' # Medium because it doesn't state *how* it's held
             snippet = not_in_person_match.group(0)
             logging.info("Found 'not in person' indicator.")
             return {'meeting_format': format_result, 'is_in_nyc': None, 'confidence': confidence, 'snippet': snippet[:500]}


        # 4. Look for Physical Location Context (if not already determined as Virtual/Hybrid)
        physical_match = self.physical_location_context_regex.search(clean_text)
        if physical_match and format_result == 'Undetermined':
             # Found a potential physical address linked to the meeting. Assume In-Person for now.
             format_result = 'In-Person'
             confidence = 'Medium' # Medium, as virtual components might be mentioned elsewhere less explicitly
             address_snippet = physical_match.group(1) # Get the captured address part
             snippet = physical_match.group(0) # Get the whole match context initially
             logging.info(f"Found potential physical location context: {address_snippet}")

             # 5. Check if the found location is NYC
             if self.nyc_regex.search(address_snippet):
                 is_nyc = True
                 confidence = 'High' # More confident if NYC match is clear within address
                 logging.info("NYC location confirmed within address snippet.")
                 snippet = address_snippet # Make snippet more specific to the address
             else:
                 is_nyc = False
                 logging.info("Physical location found, but does not appear to be NYC.")
                 snippet = address_snippet

             # Refinement: Check again for virtual keywords *near* this physical match
             # If virtual keywords found nearby, it might be Hybrid after all, or poorly worded virtual description
             search_window = clean_text[max(0, physical_match.start()-300):physical_match.end()+300]
             if self.virtual_only_regex.search(search_window) or re.search(r'(?i)\b(?:virtual|online|webcast|remote)\b', search_window):
                  # If strong virtual terms are very close, it's ambiguous or Hybrid
                  # Let's downgrade confidence or flag as ambiguous/potentially Hybrid
                  format_result = 'Undetermined' # Revert to Undetermined due to ambiguity
                  confidence = 'Low'
                  snippet = f"Ambiguous: Found physical address '{address_snippet}' but also virtual terms nearby: {search_window[max(0, physical_match.start()-300 - (max(0, physical_match.start()-300))):100]}..." # Show context
                  is_nyc = None # Reset NYC flag due to ambiguity
                  logging.warning(f"Ambiguity detected: Physical address found near virtual terms. Snippet: {snippet}")


        # 6. Final Decision
        if format_result == 'Undetermined':
             snippet = "Could not reliably determine meeting format or location from text."
             logging.info("Analysis complete: Format Undetermined.")


        return {'meeting_format': format_result, 'is_in_nyc': is_nyc, 'confidence': confidence, 'snippet': snippet[:500]} # Limit snippet length