import re
import string

from util.geo import InvalidLocationException, Location


class LibrarySearchQuery:
    """Object representing a user-submitted search for Libraries"""
    ##### Class Constants ####################################################  # noqa: E266
    SIMPLE_POSTCODE_RE = re.compile(r'''^(?:[0-9]{5}|[0-9]{9})$''')     # 5 or 9 digits

    US_STATES = {
        "AL": "Alabama",
        "AK": "Alaska",
        "AR": "Arkansas",
        "AZ": "Arizona",
        "CA": "California",
        "CO": "Colorado",
        "CT": "Connecticut",
        "DC": "District of Columbia",
        "DE": "Delaware",
        "FL": "Florida",
        "GA": "Georgia",
        "HI": "Hawaii",
        "IA": "Iowa",
        "ID": "Idaho",
        "IL": "Illinois",
        "IN": "Indiana",
        "KS": "Kansas",
        "KY": "Kentucky",
        "LA": "Louisiana",
        "MA": "Massachusetts",
        "MD": "Maryland",
        "ME": "Maine",
        "MI": "Michigan",
        "MN": "Minnesota",
        "MO": "Missouri",
        "MS": "Mississippi",
        "MT": "Montana",
        "NC": "North Carolina",
        "ND": "North Dakota",
        "NE": "Nebraska",
        "NH": "New Hampshire",
        "NJ": "New Jersey",
        "NM": "New Mexico",
        "NV": "Nevada",
        "NY": "New York",
        "OH": "Ohio",
        "OK": "Oklahoma",
        "OR": "Oregon",
        "PA": "Pennsylvania",
        "PR": "Puerto Rico",
        "RI": "Rhode Island",
        "SC": "South Carolina",
        "SD": "South Dakota",
        "TN": "Tennessee",
        "TX": "Texas",
        "UT": "Utah",
        "VA": "Virginia",
        "VT": "Vermont",
        "WA": "Washington",
        "WI": "Wisconsin",
        "WV": "West Virginia",
        "WY": "Wyoming",
    }

    US_STATE_ABBREVIATIONS = list(US_STATES.keys())

    US_STATE_NAMES = list(US_STATES.values())

    LIBRARY_KEYWORDS = [
        'archive',
        'bookmobile',
        'bookmobiles',
        'college',
        'free',
        'library',
        'memorial',
        'public',
        'regional',
        'research',
        'university',
    ]

    MAX_SEARCH_STRING_LEN = 128

    # Search Types
    GEOTARGET_SINGLE = "geotarget_single"
    GEOTARGET_MULTIPLE = "geotarget_multiple"
    LIBTARGET = "libtarget"

    ##### Public Interface / Magic Methods ###################################  # noqa: E266
    def __init__(self, raw_search_string, location=None):
        if isinstance(raw_search_string, str):
            self.raw_string = raw_search_string[:(self.MAX_SEARCH_STRING_LEN * 3)]
        else:
            self.raw_string = ''

        self.normalized_string = self._normalize_search_string(raw_search_string)
        self.raw_tokens = self.normalized_string.split()
        self.cleaned_string = self.normalized_string.translate(str.maketrans('', '', string.punctuation)).lower()
        self.tokens = self.cleaned_string.split()
        self.us_postcodes = list(filter(lambda x: self.SIMPLE_POSTCODE_RE.match(x), self.tokens))
        self.us_state_abbrs = list(filter(lambda x: x.upper() in self.US_STATE_ABBREVIATIONS, self.tokens))
        self.us_state_names = [x.lower() for x in self.US_STATE_NAMES if x.lower() in self.cleaned_string.lower()]
        self.library_keywords = list(filter(lambda x: x in self.LIBRARY_KEYWORDS, self.tokens))

        if location and not isinstance(location, Location):
            try:
                location = Location(location)
            except InvalidLocationException:
                location = None

        self.location = location

        self.search_type = self._search_type()
        self.geotargets = self._geotargets()

    def __bool__(self):
        return False if self.raw_string == '' else True

    def __str__(self):
        return self.normalized_string

    def run(self):
        """
        Return between 3 and 20 Libraries which best correspond to a given combination of user
        location and user-provided, textual search term(s). May return 0 Libraries in response
        to an invalid searchterm paired with an unknown location.

        Terminology:

            LOCATION    - The user's actual location, which we may or may not know.
                          For discussion purposes may be 'unknown' or 'known'.
            SEARCHTERM  - The user-provided, textual search term(s).
            GEOTARGET   - A geographic place/polygon derived from SEARCHTERM.
                          Valid types are 'postcode', 'city', 'county', 'state', 'nation', or 'everywhere'
            LIBTARGET   - A Library derived from SEARCHTERM
            LIB_LOCAL   - The local Library for a given GEOTARGET. Defined as a Library whose
                          focus area is based on a postcode, city, or county, whose point-based
                          location is the least distance from a polygon edge of the GEOTARGET.
            LIB_SUPRA   - A supra-local Library for a given GEOTARGET. Defined as a Library
                          whose focus area is based on a state, or is everywhere, whose point-based
                          location is the least distance from a polygon edge of the GEOTARGET.
            FOCUS_AREA  - The area a Library focuses its efforts on. Defined as one or more
                          geographic places/polygons.
            RESULT_1    - The first Library in the returned result set
            RESULT_2    - The second Library in the returned result set
            RESULT_3    - The third Library in the returned result set
            RESULT_N    - Some Library in the result set beyond RESULT_3

        Here are the criteria we use to determine the 'best' results for a request:

            1. Parse the submitted SEARCHTERM:
                - Assume SEARCHTERM refers to GEOTARGET(s) or LIBTARGET(s), but not both
                - Attempt to use the parsed SEARCHTERM to identify GEOTARGET(s)
                    - Prioritize matching on postcode, city name, state name
                - Failing that, attempt to identify LIBTARGET(s)
                    - Attempt fuzzy string matching on name, alias, description
            2. If we decide that SEARCHTERM references a single GEOTARGET:
                - LOCATION is ignored
                - Only 3 Libraries will be returned
                - Only Libraries whose FOCUS_AREA is within 300km of GEOTARGET are considered
                a. If GEOTARGET is a postcode, city, or county
                    - RESULT_1 should be LIB_LOCAL, or empty if no LIB_LOCAL exists for GEOTARGET
                    - RESULT_2 should be closest LIB_SUPRA
                    - RESULT_3 is closest local Library that is not LIB_LOCAL or next closest LIB_SUPRA
                b. If GEOTARGET is a state
                    - TBD
                c. If GEOTARGET is a nation
                    - TBD
            3. If we decide that SEARCHTERM references multiple GEOTARGETs:
                a. If LOCATION is known:
                    - Only 3 Libraries will be returned
                    - The single GEOTARGET of interest is the one closest to LOCATION
                    - Using that GEOTARGET, proceed as in item 2
                b. If LOCATION is unknown:
                    - Up to 20 Libraries will be returned
                    - The pre-limit result set will be all Libraries in all of the GEOTARGETs
                    - RESULT_1 through RESULT_20 are the first 20 Libraries found for all the
                      referenced GEOTARGETs, ordered alphabetically
            4. If we decide that SEARCHTERM references a LIBTARGET:
                a. If LOCATION is known:
                    - Only 3 Libraries will be returned
                    - RESULT_1 through RESULT_3 are Library name matches
                    - Results are ordered by ascending distance from LOCATION
                b. If LOCATION is unknown:
                    - Up to 20 Libraries will be returned
                    - RESULT_1 through RESULT_N are Library name matches
                    - Results are ordered by name match type: Name, Alias, Description
            5. If we decide the SEARCHTERM is incapable of matching any GEOTARGET or LIBTARGET:
                - We have nothing to go on, return an empty result set
        """
        if not self and not self.location:      # No valid search or user location, nothing to do
            return []

        search_method = self._appropriate_search_method()

        return search_method()

    ##### Private Methods ####################################################  # noqa: E266
    def _search_type(self):
        """Returns one of the search type constants, like LibrarySearchQuery.GEOTARGET_SINGLE"""
        search_type = None
        all_geotarget_indicators = set(self.us_postcodes) | set(self.us_state_abbrs) | set(self.us_state_names)

        if len(all_geotarget_indicators) == 1:
            search_type = self.GEOTARGET_SINGLE
        elif len(all_geotarget_indicators) > 1:
            search_type = self.GEOTARGET_MULTIPLE

        return search_type

    def _geotargets(self):
        """Returns a list of one or more geotargets extracted from the search string"""

    def _appropriate_search_method(self):
        """
        Based on the search string and user location (if any), return the search method
        that best matches the overall decision tree for Library search.
        """
        if self.target_type == self.GEOTARGET_SINGLE:
            search_method = self._search_single_geotarget

        elif self.target_type == self.GEOTARGET_MULTIPLE:
            if self.location:
                search_method = self._search_multiple_geotargets_with_location
            else:
                search_method = self._search_multiple_geotargets_without_location

        elif self.target_type == self.LIBTARGET:
            if self.location:
                search_method = self._search_libtargets_with_location
            else:
                search_method = self._search_libtargets_without_location

        else:
            search_method = lambda: []          # noqa: E731

        return search_method

    def _search_single_geotarget(self):
        """
        Search criteria once we determine the user is looking for a single geotarget:

            * LOCATION is ignored
            * Only 3 Libraries will be returned
            * Only Libraries whose FOCUS_AREA is within 300km of GEOTARGET are considered
                a. If GEOTARGET is a postcode, city, or county
                    * RESULT_1 should be LIB_LOCAL, or empty if no LIB_LOCAL exists for GEOTARGET
                    * RESULT_2 should be closest LIB_SUPRA
                    * RESULT_3 is closest local Library that is not LIB_LOCAL or next closest LIB_SUPRA
                b. If GEOTARGET is a state
                    * TBD
                c. If GEOTARGET is a nation
                    * TBD
        """

    def _search_multiple_geotargets_with_location(self):
        pass

    def _search_multiple_geotargets_without_location(self):
        pass

    def _search_libtargets_with_location(self):
        pass

    def _search_libtargets_without_location(self):
        pass

    ##### Properties and Getters/Setters #####################################  # noqa: E266

    ##### Class Methods ######################################################  # noqa: E266

    ##### Private Class Methods ##############################################  # noqa: E266
    @classmethod
    def _correct_common_search_string_errors(cls, raw_search_string):
        """
        Returns a search string that has been corrected for a set of the most common
        typos and missspellings.
        """

    @classmethod
    def _normalize_search_string(cls, raw_search_string):
        """
        Normalize a raw search string by removing extraneous whitespace and limiting the total
        size to LibrarySearchQuery.MAX_SEARCH_STRING_LEN. Also makes sure that the truncated
        version does not end in a partial word.
        """
        # Step 0: If we got bad input, don't bother with any of the normalization stuff
        if (
            not raw_search_string or
            not isinstance(raw_search_string, str) or
            raw_search_string == ''
        ):
            return ''

        # Step 1: Truncate to 3x max length, to avoid doing anything expensive to a huge string
        long_raw_search_string = raw_search_string[:(cls.MAX_SEARCH_STRING_LEN * 3)]

        # Step 2: Normalize the whitespace and tokenize
        long_raw_search_string = ' '.join(long_raw_search_string.split())
        long_raw_tokens = long_raw_search_string.split()

        # Step 3: Create a version that's cut down to our actual maximum length
        search_string = long_raw_search_string[:cls.MAX_SEARCH_STRING_LEN]
        search_string_tokens = search_string.split()

        # Step 4: Compare the last token of the one we just cut down to the same token
        #         in the tokenized version of the 3x long one. If they're different, we
        #         ended up with a partial word at the end, and we need to get rid of it.
        if search_string_tokens[-1] != long_raw_tokens[len(search_string_tokens) - 1]:
            search_string_tokens.pop()

        return ' '.join(search_string_tokens)
