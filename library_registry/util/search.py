"""
Classes and methods related to searching for Libraries.

Class names prefixed with LS for 'Library Search'.

Usage:

    Search results are obtained by calling the .run() method of an LSQuery instance that was
    instantiated with the raw string the search will be based on, and optionally a location,
    which must be an instance of library_registry.util.geo.Location.

    For example:

        user_location = Location((latitude, longitude))
        raw_search_string = 'Alameda County Library'
        search_instance = LSQuery(raw_search_string, user_location)
        found_libraries = search_instance.run()

Implementation Overview:

    The full search heuristic is detailed in the docstring for LSQuery.run(). As a high level
    summary, any particular search is assumed to be EITHER geographic (the user wants libraries
    near some point or points on earth), or name-based (the user wants libraries whose names match
    some or all of their search string).

Classes:

    - LSToken - a single token of a user-submitted search, having a value (a string of one or
        more words) and a type (indicating what the token is assumed to represent, like the
        name of a state, or a library name, or a postal code--or None if we haven't decided a type).

        Examples:

            - <LSToken(value='apple', type=None)>
            - <LSToken(value='12345', type=LSToken.POSTCODE)>
            - <LSToken(value='new mexico', type=LSToken.STATE_NAME)>

    - LSTokenSequence - a sequence of one or more LSToken objects, used as a container for
        maintaining the order of search terms while they are being evaluated to try to assign
        appropriate types, which happens largely through LSTokenSequence.merge_multiword_tokens().

        Examples:

            - <LSTokenSequence(tokens=[<LSToken(value='apple', type=None)>, <LSToken(value='banana', type=None)>])>
            - <LSTokenSequence(tokens=[<LSToken(value='new', type=None)>, <LSToken(value='mexico', type=None)>])>
            - <LSTokenSequence(tokens=[<LSToken(value='new mexico', type=LSToken.STATE_NAME)>])>

    - LS*TokenClassifier - classes that stem from LSBaseTokenClassifier, with class methods that
        take LSTokenSequence instances as input, and return copies of those sequences augmented
        according to the particular rules of the class. For instance, LSSinglewordTokenClassifier
        is responsible for assigning types to all LSToken objects in a sequence which match particular
        patterns, such as assigning a string made of 5 or 9 digits the type POSTCODE.

    - LSQuery - an umbrella class which orchestrates and executes a search. It does so in general terms by:

            1. Cleaning, normalizing, and tokenizing the user-supplied search string
            2. Running classifiers on the resulting sequence of tokens to add contextual search cues
                in the form of LSToken type values
            3. Using the classified token sequence and the user's location (if supplied) to
                determine an appropriate search method to execute (such as _search_single_geotarget())
            4. Executing the search and returning a list of found Libraries

"""
import copy
import re
import string

from sqlalchemy import func
from sqlalchemy.sql.expression import or_

from library_registry.constants import (
    LIBRARY_KEYWORDS,
    MULTI_WORD_STATE_NAMES,
    US_STATE_ABBREVIATIONS,
    US_STATE_NAMES,
)
from library_registry.util.geo import InvalidLocationException, Location


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

    COUNTY_WORDS = ['county', 'parish']

    ##### Public Interface / Magic Methods ###################################  # noqa: E266
    def __init__(self, token_string, token_type=None):
        if not isinstance(token_string, str):
            raise InvalidLSToken(f"Cannot create an LSToken with a value of '{token_string}'")

        self.value = " ".join(token_string.strip().split())
        self.type = token_type if token_type in self.VALID_TOKEN_TYPES else None

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"<LSToken(value='{self.value}', type='{self.type}')>"

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
    MAX_MULTIWORD_TOKEN_LEN = 6

    ##### Public Interface / Magic Methods ###################################  # noqa: E266
    def __init__(self, tokens):
        self.tokens = []

        for token in tokens:
            if not isinstance(token, LSToken):
                token = LSToken(token)

            self.tokens.append(token)

    def __str__(self):
        return ' '.join([t.value for t in self.tokens])

    def __repr__(self):
        return '<LSTokenSequence(tokens=[' + ', '.join([repr(t) for t in self.tokens]) + ']>'

    def __len__(self):
        return len(self.tokens)

    def __iter__(self):
        yield from self.tokens

    def __getitem__(self, key):
        return self.tokens[key]

    def merge_multiword_tokens(self, target_list, merged_token_type):
        found_targets = self._multiword_targets_found_in_sequence(target_list)

        # Go in order from longest to shortest found target
        for target_string in sorted(found_targets, key=lambda x: len(x.split()), reverse=True):
            words_in_target = target_string.split()
            new_tokens = []
            skip_next = 0

            for (token_idx, token_obj) in enumerate(self):
                # A merge has already consumed this token, skip ahead
                if skip_next > 0:
                    skip_next -= 1
                    continue

                num_words_remaining = len(' '.join([x.value for x in self[token_idx:]]).split())

                # There aren't enough remaining words to match this target, break out
                if num_words_remaining < len(words_in_target):
                    new_tokens = new_tokens + self[token_idx:]
                    break

                if token_obj.value.startswith(words_in_target[0]):
                    tokens_to_merge = [token_obj]
                    next_token_idx = token_idx + 1
                    full_match = False
                    while (
                        target_string.startswith(' '.join([x.value for x in tokens_to_merge]))
                        and next_token_idx < len(self)
                        and not full_match
                    ):
                        tokens_to_merge.append(self[next_token_idx])
                        next_token_idx += 1
                        if target_string == ' '.join([x.value for x in tokens_to_merge]):
                            full_match = True

                    if full_match:
                        new_token_value = ' '.join([x.value for x in tokens_to_merge])
                        new_tokens.append(LSToken(new_token_value, token_type=merged_token_type))
                        skip_next = len(tokens_to_merge) - 1

                if skip_next == 0:
                    new_tokens.append(token_obj)

            self.tokens = new_tokens

    ##### Private Methods ####################################################  # noqa: E266

    def _multiword_targets_found_in_sequence(self, target_list):
        """
        Given a list of target strings, return a list of those which:

            - Have between 2 and max_words number of words (where max_words may be reduced to
              the value of LSTokenSequence.MAX_MULTIWORD_TOKEN_LEN); AND
            - appear in the stringified version of this object's token list AND
            - do not split tokens when matching--for example in the following sequence:

                [LSToken('alpha'), LSToken('bravo charlie'), LSToken('delta echo')]

              the target "alpha bravo charlie" could be made from entire tokens, but the
              target "charlie delta" would split the second and third tokens, and therefore
              would not be valid.

        This should return all target strings which are possible to find in the current sequence,
        though it doesn't guarantee you'll be able to merge all of them, since an early merge
        might prevent a later one.
        """
        normalized_targets = self._normalize_target_list(target_list)
        max_words_in_a_target = max(len(x.split()) for x in normalized_targets)
        min_words_allowed = 2
        max_words_allowed = max(2, min(max_words_in_a_target, self.MAX_MULTIWORD_TOKEN_LEN))

        validated_targets = set([x for x in normalized_targets
                                 if min_words_allowed <= len(x.split()) <= max_words_allowed])
        found_targets = []

        # This bit is a little non-intuitive. What it's doing is creating a string of all the token
        # values, where internal spaces are preserved, but the points between one token and the next
        # are replaced by '##'. Then, for each target string, it creates a regex pattern that means
        # "only return a match if this string starts and ends at token boundaries."
        token_boundaries_string = r'#' + r'##'.join([t.value for t in self]) + r'#'

        for target in validated_targets:
            target_pattern = r'#' + r'( |##)'.join(target.split()) + r'#'
            if re.search(target_pattern, token_boundaries_string):
                found_targets.append(target)

        return found_targets

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

    @classmethod
    def _normalize_target_list(cls, target_list):
        """
        For a list of target strings, strip extraneous whitespace and convert to lowercase.
        """
        normalized_targets = []
        for t in target_list:
            normalized_targets.append(' '.join(t.split()).lower())

        return normalized_targets


class LSBaseTokenClassifier:
    """
    Subclassed to represent a meaningful pattern within a sequence of tokens.

    When run on a sequence of tokens, it returns a copy which may be augmented by (re-)classifying
    tokens, merging tokens, etc., based on the pattern the instance describes.
    """
    @classmethod
    def classify(cls, tokens=None):
        """ABSTRACT: Return an augmented copy of the token list"""
        raise NotImplementedError("LSTokenClassifier.classify_tokens() is abstract")

    @classmethod
    def work_to_do(cls, token_sequence):
        """
        Should return True if there is likely to be work that the classifier can do, False otherwise.
        """
        if token_sequence.all_classified:
            return False
        else:
            return True


class LSSinglewordTokenClassifier(LSBaseTokenClassifier):
    """Attempts to classify single-word tokens."""
    @classmethod
    def classify(cls, token_sequence):
        """
        For a given string token, attempt to classify it as a specific type.

        Note that this function should ONLY be used for types that can be associated with
        a single word.
        """
        if not cls.work_to_do(token_sequence):
            return token_sequence

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
                token_obj.type = LSToken.LIBRARY_KEYWORD

        return augmented


class LSStatenameTokenClassifier(LSBaseTokenClassifier):
    """
    Attempts to classify tokens representing the name of a US State.
    """
    @classmethod
    def classify(cls, token_sequence):
        if not cls.work_to_do(token_sequence):
            return token_sequence

        augmented = copy.deepcopy(token_sequence)

        for token_obj in augmented:
            if token_obj.type is not None:
                continue
            elif token_obj.value in US_STATE_NAMES:
                token_obj.type = LSToken.STATE_NAME

        max_tokens_in_state_names = max([len(x.split(' ')) for x in MULTI_WORD_STATE_NAMES])
        return augmented.merge_multiword_tokens(
            target_list=MULTI_WORD_STATE_NAMES,
            merged_token_type=LSToken.STATE_NAME,
            max_words=max_tokens_in_state_names
        )


class LSCitynameTokenClassifier(LSBaseTokenClassifier):
    """
    Attempts to classify tokens representing the name of a City.

    Should be run after state names and abbreviations are classified, as the presence of state name or
    abbreviation tokens is used to potentially infer the presence of a city name.
    """
    STATE_TOKEN_TYPES = [LSToken.STATE_ABBR, LSToken.STATE_NAME]

    @classmethod
    def work_to_do(cls, token_sequence):
        # No work possible if there's only one token, or all tokens already classified
        if len(token_sequence) == 1 or token_sequence.all_classified:
            return False

        # If any of these conditions are true there might be work to do
        if (
            'city' in str(token_sequence) or                                # Bare-word 'city' in tokens
            any([x.type in cls.STATE_TOKEN_TYPES for x in token_sequence])  # A state name or abbreviation appears
        ):
            return True

        return False

    @classmethod
    def classify(cls, token_sequence):
        """
        Patterns that may indicate a city name:

            * If there is an unclassified token whose value is 'city', with unclassified
              tokens before it
            * If there are two unclassified tokens 'city' 'of' in sequence, with unclassified
              tokens after them
            * If a state name or abbreviation follows 1+ unclassified tokens
        """
        if not cls.work_to_do(token_sequence):
            return token_sequence

        augmented = copy.deepcopy(token_sequence)
        tokens_as_string = str(augmented)
        tokens_len = len(augmented)

        # Pattern 1: Sequential unclassified words 'city of' in tokens
        if 'city of' in tokens_as_string:
            # In this case, we will create a multi-word token starting with 'city of', and
            # include the unclassified tokens which follow up to either the next classified
            # token, or the end of the sequence.
            for (token_idx, token_obj) in enumerate(augmented[:-2]):
                if (
                    token_obj.value == 'city' and           # 'city', followed by
                    augmented[token_idx+1].value == 'of'    # 'of', followed by
                    and not augmented[token_idx+2].type     # at least one unclassified token
                ):
                    compound_word = ' '.join([x.value for x in augmented[token_idx:(token_idx+3)]])
                    next_token_idx = token_idx + 3
                    while next_token_idx < tokens_len and augmented[next_token_idx].type is None:
                        compound_word = compound_word + ' ' + augmented[next_token_idx].value
                        next_token_idx += 1

                    augmented.merge_multiword_tokens(target_list=[compound_word],
                                                     merged_token_type=LSToken.CITY_NAME,
                                                     max_words=len(compound_word.split()))
                    break

        # Pattern 2: Unclassified word 'city' in tokens (but no 'city of')
        elif 'city' in tokens_as_string:
            # We'll create a multi-word token from the sequence of unclassified tokens preceding 'city',
            # and the 'city' token itself.
            for (token_idx, token_obj) in enumerate(augmented):
                if (
                    token_idx > 0 and                   # we're past the first word, and find
                    token_obj.value == 'city' and       # 'city', preceded by
                    not augmented[token_idx-1].type     # at least one unclassified token
                ):
                    compound_word = ' '.join([x.value for x in augmented[token_idx-1:token_idx+1]])
                    prev_token_idx = token_idx - 2
                    while prev_token_idx >= 0 and augmented[prev_token_idx].type is None:
                        compound_word = augmented[prev_token_idx].value + ' ' + compound_word
                        prev_token_idx -= 1

                    augmented.merge_multiword_tokens(target_list=[compound_word],
                                                     merged_token_type=LSToken.CITY_NAME,
                                                     max_words=len(compound_word.split()))
                    break

        # Pattern 3: A state name or abbreviation preceded by unclassified tokens
        elif any([x.type in cls.STATE_TOKEN_TYPES for x in token_sequence]):
            # Create a multi-word token from the sequence of unclassified tokens preceding the
            # state name or abbreviation
            for (token_idx, token_obj) in enumerate(augmented):
                if (
                    token_idx > 0 and                               # past the first word, and
                    token_obj.type in cls.STATE_TOKEN_TYPES and     # find a state token
                    not augmented[token_idx-1].type                 # preceded by 1+ unclassified tokens
                ):
                    if (token_idx - 2) < 0 or augmented[token_idx-2].type:
                        # only a single unclassified word precedes the statename, just update its type
                        augmented[token_idx-1].type = LSToken.CITY_NAME
                    else:
                        # we need to merge a run of unclassified words
                        compound_word = augmented[token_idx-1].value
                        prev_token_idx = token_idx - 2
                        while prev_token_idx >= 0 and augmented[prev_token_idx].type is None:
                            compound_word = augmented[prev_token_idx].value + ' ' + compound_word
                            prev_token_idx -= 1

                        augmented.merge_multiword_tokens(target_list=[compound_word],
                                                         merged_token_type=LSToken.CITY_NAME,
                                                         max_words=len(compound_word.split()))
                        break

        return augmented


class LSCountynameTokenClassifier(LSBaseTokenClassifier):
    """Attempts to classify tokens representing the name of a County"""
    @classmethod
    def work_to_do(cls, token_sequence):
        """
        If one of the words in LSToken.COUNTY_WORDS appears in the token sequence, there's probably work.
        """
        if bool(set(LSToken.COUNTY_WORDS) & set([x.value for x in token_sequence])):
            return True
        return False

    @classmethod
    def classify(cls, token_sequence):
        """
        Patterns that probably indicate a county name:

            * If there is an unclassified token whose value is a word in LSToken.COUNTY_WORDS,
                preceded by 1+ unclassified tokens
        """
        if not cls.work_to_do(token_sequence):
            return token_sequence

        augmented = copy.deepcopy(token_sequence)

        for (token_idx, token_obj) in enumerate(augmented):
            if (
                token_idx > 0 and                               # we're past the first word, and find
                token_obj.value in LSToken.COUNTY_WORDS and     # a county word, preceded by
                not augmented[token_idx-1].type                 # at least one unclassified token
            ):
                compound_word = ' '.join([x.value for x in augmented[token_idx-1:token_idx+1]])
                prev_token_idx = token_idx - 2
                while prev_token_idx >= 0 and augmented[prev_token_idx].type is None:
                    compound_word = augmented[prev_token_idx].value + ' ' + compound_word
                    prev_token_idx -= 1

                augmented.merge_multiword_tokens(target_list=[compound_word],
                                                 merged_token_type=LSToken.COUNTY_NAME,
                                                 max_words=len(compound_word.split()))
                break

        return augmented


class LSLibrarynameTokenClassifier(LSBaseTokenClassifier):
    """Attempts to classify tokens representing the name of a Library"""
    @classmethod
    def work_to_do(cls, token_sequence):
        """
        If one of the words in LIBRARY_KEYWORDS is in the token sequence, probably work to do.
        """
        if (
            any([bool(x.type == LSToken.LIBRARY_KEYWORD) for x in token_sequence])
            or bool(set(LIBRARY_KEYWORDS) & set([x.value for x in token_sequence]))
        ):
            return True
        return False

    @classmethod
    def classify(cls, token_sequence):
        """
        If one of the LIBRARY_KEYWORDS appears, a multi-word token of type LSToken.LIBRARY_NAME will be
        created from all sequential tokens before and after that are either unclassified or of type
        LSToken.LIBRARY_KEYWORD.
        """
        if not cls.work_to_do(token_sequence):
            return token_sequence

        augmented = copy.deepcopy(token_sequence)
        tokens_len = len(augmented)

        for (token_idx, token_obj) in enumerate(augmented):
            if (
                token_obj.type == LSToken.LIBRARY_KEYWORD or    # a pre-classified keyword
                token_obj.value in LIBRARY_KEYWORDS             # an unclassified keyword
            ):
                compound_word = token_obj.value

                # find preceding tokens
                prev_token_idx = token_idx - 1
                while prev_token_idx >= 0 and augmented[prev_token_idx].type in [None, LSToken.LIBRARY_KEYWORD]:
                    compound_word = augmented[prev_token_idx].value + ' ' + compound_word
                    prev_token_idx -= 1

                # find following tokens
                next_token_idx = token_idx + 1
                while next_token_idx < tokens_len and augmented[next_token_idx].type in [None, LSToken.LIBRARY_KEYWORD]:
                    compound_word = compound_word + ' ' + augmented[next_token_idx].value
                    next_token_idx += 1

                augmented.merge_multiword_tokens(target_list=[compound_word],
                                                 merged_token_type=LSToken.LIBRARY_NAME,
                                                 max_words=len(compound_word.split()))

        return augmented


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
