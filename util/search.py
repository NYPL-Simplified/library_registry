"""
Classes and methods related to searching for Libraries.

Class names prefixed with LS for 'Library Search'.
"""
import copy
import re
import string

from sqlalchemy import func
from sqlalchemy.sql.expression import or_

from constants import (
    LIBRARY_KEYWORDS,
    MULTI_WORD_STATE_NAMES,
    US_STATE_ABBREVIATIONS,
    US_STATE_NAMES,
)
from util.geo import InvalidLocationException, Location


SIMPLE_POSTCODE_RE = re.compile(r'''^(?:[0-9]{5}|[0-9]{9})$''')     # 5 or 9 digits


class InvalidLSToken(Exception):
    """Raised when an LSToken is created from a bad value"""


class LSToken:
    """
    Object representing a single token in a user-submitted search for Libraries.

    Notes:

        * An LSToken's .value may be comprised of more than one word. For instance, a single
          token of type STATE_NAME could have the value "new york".
        * LSToken instances are fairly inert containers, mostly meant to allow classifying
          a single- or multi-word string with a meaningful token type.
    """
    ##### Class Constants ####################################################  # noqa: E266

    # Token Types
    POSTCODE        = "postcode"            # noqa: E221
    STATE_ABBR      = "state_abbr"          # noqa: E221
    STATE_NAME      = "state_name"          # noqa: E221
    COUNTY_NAME     = "county_name"         # noqa: E221
    CITY_NAME       = "city_name"           # noqa: E221
    LIBRARY_KEYWORD = "library_keyword"     # noqa: E221
    LIBRARY_NAME    = "library_name"        # noqa: E221

    VALID_TOKEN_TYPES = [
        POSTCODE,
        STATE_ABBR,
        STATE_NAME,
        COUNTY_NAME,
        CITY_NAME,
        LIBRARY_KEYWORD,
        LIBRARY_NAME,
    ]

    ##### Public Interface / Magic Methods ###################################  # noqa: E266
    def __init__(self, token_string, token_type=None):
        if not isinstance(token_string, str):
            raise InvalidLSToken(f"Cannot create an LSToken with a value of '{token_string}'")

        self.value = " ".join(token_string.strip().split())
        self.type = token_type if token_type in self.VALID_TOKEN_TYPES else None

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"<LSToken(value={self.value}, type={self.type})>"

    def __eq__(self, other):
        return True if self.value == other.value else False

    ##### Private Methods ####################################################  # noqa: E266

    ##### Properties and Getters/Setters #####################################  # noqa: E266
    @property
    def is_multiword(self):
        return bool(' ' in self.value)

    ##### Class Methods ######################################################  # noqa: E266

    ##### Private Class Methods ##############################################  # noqa: E266


class LSTokenSequence:
    """A sequence of LSToken objects"""
    ##### Class Constants ####################################################  # noqa: E266

    # When searching for and combining single-word search tokens into multi-word tokens (as in
    # ["district", "of", "columbia"] ==> ["district of columbia"]), this is the maximum number
    # of single tokens that merge_multiword_tokens() will attempt to scan, no matter what is
    # passed in as the 'max_words' parameter.
    MAX_MULTIWORD_TOKEN_LEN = 5

    ##### Public Interface / Magic Methods ###################################  # noqa: E266
    def __init__(self, tokens):
        self.tokens = []

        for token in tokens:
            if not isinstance(token, LSToken):
                token = LSToken(token)

            self.tokens.append(token)

    def __str__(self):
        return ' '.join([t.value for t in self.tokens])

    def __len__(self):
        return len(self.tokens)

    def unclassified_run_before_idx(self, idx_position):
        """Returns a list of the consecutive unclassified tokens immediately prior to idx_position"""
        n_tokens = len(self)
        output = []

        if idx_position == 0 or n_tokens == 1 or self.all_classified:   # Nothing to look for
            return output

        return output

    def unclassified_run_after_idx(self, idx_position):
        """Returns a list of the consecutive unclassified tokens immediately following idx_position"""

    def merge_multiword_tokens(self, target_list, merged_token_type, max_words=3):
        """
        Given a list of multi-word string targets, identify and merge sequential, unclassified
        tokens in the current LSTokenSequence which, when joined by spaces, appear in the list
        of target strings.

        Alters the current object's .tokens list in place.

        Parameters:

            target_list         - iterable of single-space separated strings to match
                                  multi-word token runs against

            merged_token_type   - a token type constant from LSToken, which
                                  will be used as the type of any token created

            max_words           - integer, the maximum number of single tokens which
                                  should be combined to form a possible multi-word token.
                                  Note that this is ignored if higher than the
                                  LSQuery.MAX_MULTIWORD_TOKEN_LEN constant,
                                  or if lower than 2.

        Notes:

            * This is a complicated function. It would be nice to decompose it if possible,
              but I'm having trouble doing so in this initial pass (2021-05-28). As a temporary
              compromise I'm adding a bunch of documentation to it. --Nick B.

            * The match process proceeds as follows:

                1. Go to the first token in the input list which
                    a. is itself unclassified (has a .type of None) and
                    b. is immediately followed by another unclassified token
                2. Starting with this token and the one following, join the values with a space
                3. Check that compound word against the strings in the target list.
                4. If that compound word is in the target list:
                    a. create a new LSToken with the compound word, typed to merged_token_type
                    b. add that token into the output list in place of the original two tokens
                    c. skip over the next token, which has now been consumed by the compound
                    d. go to the next token in the list that satisfies step 1.
                5. If the 2-word token is not in the target list, try 3, 4, 5 word tokens stemmed
                   from the current token, if there is a run of unclassified tokens to support that.
                6. If any of those match (with the number of tokens forming a compound being limited
                   by the max_words parameter and associated constants), follow the procedure in 4.
                7. If no compound word stemmed off the current token matched a target, add the
                   current token to the output list as-is, and proceed to the next token satisfying 1.

            * A single unclassified input token will never be merged into more than a single compound token.
              Consequently, if a target list included both "alpha bravo" and "alpha bravo charlie", and the
              input included an unclassified run of "alpha", "bravo", "charlie", the output would be a list of
              two tokens, "alpha bravo" and "charlie".
        """
        # Step 1: Find out if we can exit this function without doing expensive work.
        if self.all_classified or self.longest_unclassified_run <= 1:
            return self.tokens       # Everything is classified or no multi-word runs are possible

        # Step 2: Make sure the maxiumum number of tokens used to form a compound word is in bounds,
        #         between 2 and the maximum number allowed by the class constant MAX_MULTIWORD_TOKEN_LEN,
        #         or the length ceiling imposed by the longest run of unclassified tokens in the input list.
        min_multiword_tokens = 2
        max_multiword_tokens = min(self.longest_unclassified_run, self.MAX_MULTIWORD_TOKEN_LEN)
        max_words = min(max(max_words, min_multiword_tokens), max_multiword_tokens)

        # Step 3: Narrow to unique targets which can be matched by the unclassified runs in this token list.
        usable_targets = set([x for x in target_list if len(x.split(' ')) <= self.longest_unclassified_run])

        if not usable_targets:
            return self.tokens       # Nothing short enough to match against, no work to do.

        # Step 4: Set up some local variables.
        total_token_count = len(self.tokens)                # total number of tokens we have to work with
        new_tokens = []                                     # the list we will eventually output
        skip_next = 0                                       # counter to skip past tokens already merged

        # Step 5: Iterate through the tokens, looking for runs to merge based on the target list.
        for (token_idx, token_obj) in enumerate(self.tokens):
            # Find out if we can jump to the next token without doing anything expensive.
            if skip_next > 0:                               # skipping tokens merged by a previous iteration, and
                skip_next = skip_next - 1                   # excluding them from output by not appending to new_tokens
                continue
            elif (
                token_obj.type or                               # this token is already classified
                token_idx == (total_token_count - 1) or         # last token in list, can't start a multi-word
                self.tokens[token_idx + 1].type is not None     # next token already classified, can't start multi-word
            ):
                new_tokens.append(token_obj)    # make sure they go into the output list if they can't be merged
                continue                        # then go to the next iteration

            # We couldn't skip ahead based on the current token object, so let's find out if we're too
            # close to the end of the list to do any more useful word stemming.
            n_tokens_left = total_token_count - token_idx           # tokens from here to the end of the list

            if n_tokens_left < min_multiword_tokens:                # not enough tokens left for a min length multi-word
                new_tokens = new_tokens + self.tokens[token_idx:]   # add the remainder of the list to the output
                break                                               # and stop iterating the tokens list

            # Find the max number of words in a row we can potentially merge, starting with the current token.
            loop_local_max_words = min(max_words, n_tokens_left)    # Don't run off the end of the list making compounds

            # if we got here, this token and the next are unclassified--lets look ahead further for a max run size
            loop_local_unclassified_run = 2
            for lookahead_token in self.tokens[(token_idx + 2):(token_idx+loop_local_max_words)]:
                if lookahead_token.type is not None:
                    break
                else:
                    loop_local_unclassified_run = loop_local_unclassified_run + 1

            loop_local_max_words = min(loop_local_max_words, loop_local_unclassified_run)

            # We got here, so we'll actually generate and check compound words starting at this index position.
            for num_words in range(min_multiword_tokens, loop_local_max_words + 1):
                slice_start = token_idx
                slice_end = token_idx + num_words
                compound_word = ' '.join([x.value for x in self.tokens[slice_start:slice_end]])

                if compound_word in usable_targets:                # We got a match!
                    new_tokens.append(LSToken(compound_word, token_type=merged_token_type))
                    skip_next = num_words - 1                      # Skip the next N-1 tokens, that are now merged
                    break                                          # with the current token_obj.

            if skip_next == 0:                  # If we got here, no compound word stemmed from the current token
                new_tokens.append(token_obj)    # matched, so we put the current token into the output as a singleton.

        self.tokens = new_tokens
        return self

    def merge_multiword_statenames(self):
        """
        For the current object's .tokens list, combine any runs of unclassified tokens that form a state name.

        Convenience function built on top of merge_multiword_tokens().
        """
        max_tokens_in_state_names = max([len(x.split(' ')) for x in MULTI_WORD_STATE_NAMES])
        return self.merge_multiword_tokens(
            target_list=MULTI_WORD_STATE_NAMES,
            merged_token_type=LSToken.STATE_NAME,
            max_words=max_tokens_in_state_names
        )

    ##### Private Methods ####################################################  # noqa: E266

    ##### Properties and Getters/Setters #####################################  # noqa: E266
    @property
    def all_classified(self):
        return all(bool(token.type is not None) for token in self.tokens)

    @property
    def unclassified_count(self):
        return len(list(filter(lambda x: x.type is None, self.tokens)))

    @property
    def longest_unclassified_run(self):
        if self.all_classified:
            return 0

        (current_run, max_run) = (0, 0)
        for token in self.tokens:
            current_run = current_run + 1 if not token.type else 0
            max_run = max(current_run, max_run)
        return max_run

    ##### Class Methods ######################################################  # noqa: E266

    ##### Private Class Methods ##############################################  # noqa: E266


class LSBaseTokenClassifier:
    """
    Abstract base class, subclassed to represent a meaningful pattern within a sequence of tokens.

    When run on a sequence of tokens, it returns a copy which may be augmented by (re-)classifying
    tokens, merging tokens, etc., based on the pattern the instance describes.
    """
    @classmethod
    def classify(cls, tokens=None):
        """ABSTRACT: Return an augmented copy of the token list"""
        raise NotImplementedError("LSTokenClassifier.classify_tokens() is abstract")

    @classmethod
    def work_to_do(cls, tokens=None):
        """ABSTRACT: Return a boolean indicating whether there is work to do in this list"""
        raise NotImplementedError("LSTokenClassifier.work_to_do() is abstract")


class LSSinglewordTokenClassifier(LSBaseTokenClassifier):
    """Attempts to classify single-word tokens."""
    @classmethod
    def work_to_do(cls, token_sequence):
        if token_sequence.all_classified:
            return False
        else:
            return True

    @classmethod
    def classify(cls, token_sequence):
        """
        For a given string token, attempt to classify it as a specific type.

        Note that this function should ONLY be used for types that can be associated with
        a single word.
        """
        augmented = copy.deepcopy(token_sequence)

        for token_obj in augmented:
            if token_obj.type is not None or token_obj.is_multiword:
                continue
            elif SIMPLE_POSTCODE_RE.match(token_obj.value):
                token_obj.type = LSToken.POSTCODE
            elif token_obj.value in US_STATE_ABBREVIATIONS:
                token_obj.type = LSToken.STATE_ABBR
            elif token_obj.value in US_STATE_NAMES:
                token_obj.type = LSToken.STATE_NAME
            elif token_obj.value in LIBRARY_KEYWORDS:
                token_obj.type = cls.LIBRARY_KEYWORD

        return augmented


class LSCitynameTokenClassifier(LSBaseTokenClassifier):
    """Attempts to classify tokens representing the name of a City"""
    STATE_TOKEN_TYPES = [LSToken.STATE_ABBR, LSToken.STATE_NAME]

    @classmethod
    def work_to_do(cls, tokens):
        if len(tokens) >= 1 or cls.all_classified(tokens):
            return False    # No work possible if there's only one token, or all tokens already classified

        tokens_as_string = " ".join([token_obj.value for token_obj in tokens])

        # If any of these conditions are true, there might be work, worth proceeding
        if (
            'city' in tokens_as_string or                           # Bare-word 'city' in tokens
            any([x.type in cls.STATE_TOKEN_TYPES for x in tokens])  # A state name or abbreviation appears
        ):
            return True
        else:
            return False

    @classmethod
    def classify(cls, tokens):
        """
        Patterns that may indicate a city name:

            * If a state name or abbreviation follows 1+ unclassified tokens
            * If there is an unclassified token whose value is 'city', with unclassified
              tokens before it
            * If there are two unclassified tokens 'city' 'of' in sequence, with unclassified
              tokens after them
        """
        if not cls.work_to_do(tokens):
            return tokens

        tokens_as_string = " ".join([token_obj.value for token_obj in tokens])
        augmented = copy.deepcopy(tokens)
        tokens_len = len(tokens)

        if 'city of' in tokens_as_string:       # Pattern 1: Bare words 'city of' in tokens
            for (token_idx, token_obj) in enumerate(tokens[:-2]):
                if (
                    token_obj.value == 'city' and           # 'city', followed by
                    tokens[token_idx+1].value == 'of'       # 'of', followed by
                    and not tokens[token_idx+2].type        # at least one unclassified token
                ):
                    compound_word = tokens[(token_idx+2)].value
                    next_token_idx = token_idx + 3
                    while next_token_idx < tokens_len and tokens[next_token_idx].type is None:
                        compound_word = compound_word + ' ' + tokens[next_token_idx]
                        next_token_idx = next_token_idx + 1

        elif 'city' in tokens_as_string:        # Pattern 2: Bare word 'city' in tokens
            ...


class LSCountynameTokenClassifier(LSBaseTokenClassifier):
    """Attempts to classify tokens representing the name of a County"""
    @classmethod
    def classify(cls, tokens):
        """
        Patterns that probably indicate a county name:

            * If there is an unclassified token whose value is 'county', following 1+
              unclassified tokens
        """
        return tokens


class LSLibrarynameTokenClassifier(LSBaseTokenClassifier):
    """Attempts to classify tokens representing the name of a Library"""
    @classmethod
    def classify(cls, tokens):
        """
        Patterns that probably indicate a Library name:

            * If there is at least 1 token of type LIBRARY_KEYWORD
        """
        return tokens


class LSQuery:
    """Object representing a user-submitted search for Libraries"""
    ##### Class Constants ####################################################  # noqa: E266

    # A list of search typos that are common enough that we just want to correct them
    # during normalization. The first term is the mistaken version, the second is what it
    # will be corrected to. Please note that as currently written, these can only be single
    # words. To fix a multi-word mistake you will need to alter _normalize_search_string().
    COMMON_MISTAKES = [
        ("libary", "library"),
    ]

    # The longest (post-normalization) search string we will consider. During normalization
    # a user-submitted search string will be truncated to this length (or slightly shorter
    # if the full length breaks in the middle of a token).
    MAX_SEARCH_STRING_LEN = 128

    # When searching for and combining single-word search tokens into multi-word tokens (as in
    # ["district", "of", "columbia"] ==> ["district of columbia"]), this is the maximum number
    # of single tokens that _merge_multiword_tokens() will attempt to scan, no matter what is
    # passed in as the 'max_words' parameter.
    MAX_MULTIWORD_TOKEN_LEN = 5

    # Search types, used to classify what kind of search we'll perform.
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
        self.cleaned_string = self.normalized_string.translate(str.maketrans('', '', string.punctuation)).lower()
        self.tokens = self._tokenize(self.cleaned_string)

        if location and not isinstance(location, Location):
            try:
                location = Location(location)
            except InvalidLocationException:
                location = None

        self.location = location
        self.search_type = self._search_type()

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
        """
        Returns one of the search type constants, like LSQuery.GEOTARGET_SINGLE.

        Here is how we decide which search type to go with:

            * If one-and-only-one token of the query is a postalcode, we return GEOTARGET_SINGLE
            * If multiple tokens are postalcodes, we return GEOTARGET_MULTIPLE
            * If a city or county name can be extracted from a query, we return GEOTARGET_SINGLE
            * If a state name (but no city, county, or postcode) is present, we return GEOTARGET_SINGLE
        """
        search_type = None
        return search_type

    def _appropriate_search_method(self):
        """
        Based on the search string and user location (if any), return the search method
        that best matches the overall decision tree for Library search.
        """
        if self.search_type == self.GEOTARGET_SINGLE:
            search_method = self._search_single_geotarget

        elif self.search_type == self.GEOTARGET_MULTIPLE:
            if self.location:
                search_method = self._search_multiple_geotargets_with_location
            else:
                search_method = self._search_multiple_geotargets_without_location

        elif self.search_type == self.LIBTARGET:
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
    @classmethod
    def fuzzy_match_clause(cls, field, value):
        """Create a SQL clause that attempts a fuzzy match of the given
        field against the given value.

        If the field's value is less than six characters, we require
        an exact (case-insensitive) match. Otherwise, we require a
        Levenshtein distance of less than two between the field value and
        the provided value.
        """
        is_long = func.length(field) >= 6
        close_enough = func.levenshtein(func.lower(field), value) <= 2
        long_value_is_approximate_match = (is_long & close_enough)
        exact_match = field.ilike(value)
        return or_(long_value_is_approximate_match, exact_match)

    ##### Private Class Methods ##############################################  # noqa: E266
    @classmethod
    def _normalize_search_string(cls, raw_search_string):
        """
        Normalize a raw search string by removing extraneous whitespace and limiting the total
        size to LSQuery.MAX_SEARCH_STRING_LEN. Also makes sure that the truncated
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

        # Step 2: Normalize the whitespace to single spaces and tokenize to single words
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

        # Step 5: Fix common mistakes.
        lc_tokens = [token.lower() for token in search_string_tokens]
        for (wrong, correct) in cls.COMMON_MISTAKES:
            mistake_positions = [idx for (idx, token) in enumerate(lc_tokens) if token == wrong.lower()]
            for pos in mistake_positions:
                search_string_tokens[pos] = correct

        return ' '.join(search_string_tokens)

    @classmethod
    def _tokenize(cls, normalized_search_string):
        """
        Return a list of LSToken objects created from words in a normalized search string.

        A token is not always a single word, depending on how the query string is parsed. For instance,
        using the query string "Los Angeles, California", we would want two tokens: "Los Angeles" and
        "California."
        """
        words = [LSToken(word) for word in normalized_search_string.split()]
        tokens = []

        if len(words) == 1 or all([bool(word.type is not None) for word in words]):
            # No multi-word tokens are possible if either a) there is only one word, or b) all
            # of the words present have been successfully individually classified by
            # LSToken.token_type() during the creation of that token instance.
            tokens = words
        else:
            tokens = cls._merge_multiword_statenames(words)
            tokens = cls._classify_tokens_by_pattern(tokens)

        return tokens

    @classmethod
    def _max_consecutive_unclassified_run(self, token_list):
        """Return a number representing the longest run of unclassified tokens in a list."""
        if all(bool(token.type is not None) for token in token_list):
            return 0

        current_run = 0
        max_run = 0
        for token in token_list:
            current_run = current_run + 1 if not token.type else 0
            max_run = max(current_run, max_run)
        return max_run

    @classmethod
    def _classify_tokens_by_pattern(cls, tokens):
        """
        For a list of LSToken objects, attempt to classify any unclassified
        tokens based on patterns present in the list.

        Notes:

            * This function should run AFTER any calls to _merge_multiword_tokens()
              (or its convenience functions) have been made. It relies on patterns
              those functions establish, such as the presence of a state name.

        Patterns looked for:

            * A state name or abbreviation following 1+ unclassified tokens, assume CITY_NAME
            * An unclassified token whose value is 'county', following 1+ unclassified tokens, assume COUNTY_NAME
            * The presence of 1+ tokens of type LIBRARY_KEYWORD, assume LIBRARY_NAME
            * An unclassified token whose value is 'city', assume CITY_NAME for preceding token(s)

        """
        return tokens
