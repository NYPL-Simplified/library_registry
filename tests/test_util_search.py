import math

import pytest

from util.search import LibrarySearchQuery


class TestLibrarySearchQuery:
    @pytest.mark.parametrize(
        "input_string,result",
        [
            pytest.param("1234", False, id="too_short_four_digits"),
            pytest.param("12345", True, id="five_digit_zip"),
            pytest.param("123456", False, id="too_long_six_digits"),
            pytest.param("123451234", True, id="nine_digit_zip4"),
            pytest.param("1234512345", False, id="too_long_ten_digits"),
        ]
    )
    def test_simple_postcode_re(self, input_string, result):
        """
        GIVEN: An input string
        WHEN:  That string is matched against LibrarySearchQuery.SIMPLE_POSTCODE_RE
        THEN:  If the string is a 5 digit or 9 digit number, a match should return
        """
        assert bool(LibrarySearchQuery.SIMPLE_POSTCODE_RE.match(input_string)) is result

    def test_boolean_context(self):
        """
        GIVEN: A search_string that is None or not a string
        WHEN:  An attempt is made to instantiate a LibrarySearchQuery object based on that search_string
        THEN:  The returned object should evaluate as False in a boolean context
        """
        assert not LibrarySearchQuery(None)
        assert not LibrarySearchQuery(12345)
        assert not LibrarySearchQuery([1, 2, 3])
        assert not LibrarySearchQuery({"a": 1})
        assert not LibrarySearchQuery((1, 2, 3))

    @pytest.mark.parametrize(
        "search_string,raw_tokens,tokens",
        [
            pytest.param("Alpha", ["Alpha"], ["alpha"]),
            pytest.param("Alpha Bravo", ["Alpha", "Bravo"], ["alpha", "bravo"]),
            pytest.param("Alpha, Bravo? Charlie!", ["Alpha,", "Bravo?", "Charlie!"], ["alpha", "bravo", "charlie"]),
            pytest.param("alpha 12345 54321-3232", ["alpha", "12345", "54321-3232"], ["alpha", "12345", "543213232"])
        ]
    )
    def test_tokenization(self, search_string, raw_tokens, tokens):
        """
        GIVEN: A search_string
        WHEN:  A LibrarySearchQuery object is instantiated from that search_string
        THEN:  The following should be true:
                * The .raw_string attribute should match the input string
                * The .raw_tokens attribute should be a list of the space separated items in the input
                * The .tokens attribute should be a list of the space separated items, less punctuation, lowercased
        """
        sq_obj = LibrarySearchQuery(search_string)
        assert sq_obj.raw_string == search_string
        assert sq_obj.raw_tokens == raw_tokens
        assert sq_obj.tokens == tokens

    @pytest.mark.parametrize(
        "search_string,us_postcodes",
        [
            pytest.param("Alpha Bravo", []),
            pytest.param("12345", ["12345"]),
            pytest.param("54321 1234 44332-2323", ["54321", "443322323"]),
        ]
    )
    def test_us_postcodes(self, search_string, us_postcodes):
        """
        GIVEN: An input string
        WHEN:  A LibrarySearchQuery object is instantiated from that search_string
        THEN:  The .us_postcodes attribute should be a list of any tokens that are 5 or 9 digit numbers
        """
        sq_obj = LibrarySearchQuery(search_string)
        assert sq_obj.us_postcodes == us_postcodes

    @pytest.mark.parametrize(
        "search_string,us_state_abbrs",
        [
            pytest.param("Alpha, Bravo", []),
            pytest.param("Alpha, NY", ["ny"]),
            pytest.param("KY alpha SC", ["ky", "sc"]),
        ]
    )
    def test_us_state_abbrs(self, search_string, us_state_abbrs):
        """
        GIVEN: An input string
        WHEN:  A LibrarySearchQuery object is instantiated from that search_string
        THEN:  The .us_states attribute should be a list of any tokens that match
               a 2-letter US state abbreviation
        """
        sq_obj = LibrarySearchQuery(search_string)
        assert sq_obj.us_state_abbrs == us_state_abbrs

    @pytest.mark.parametrize(
        "search_string,us_state_names",
        [
            pytest.param("New York, New York", ["new york"], id="new_york_ny"),
            pytest.param("greenville south carolina", ["south carolina"], id="greeneville_sc"),
            pytest.param("wyoming", ["wyoming"], id="wyoming"),
            pytest.param("Alaska Maryland South Dakota", ["alaska", "maryland", "south dakota"], id="multiple_states"),
            pytest.param("New      ?Jersey", ["new jersey"], id="extra_spaces_punctuation"),
            pytest.param("Philadelphia", [], id="no_state_name"),
        ]
    )
    def test_us_state_names(self, search_string, us_state_names):
        """
        GIVEN: An input string
        WHEN:  A LibrarySearchQuery object is instantiated from that string
        THEN:  The .us_state_names attribute should be list of lowercase state names, for
               any US states whose name appeared in the search string
        """
        sq_obj = LibrarySearchQuery(search_string)
        assert sq_obj.us_state_names == us_state_names

    @pytest.mark.parametrize(
        "search_string,library_keywords",
        [
            pytest.param("Alpha, Bravo", []),
            pytest.param("New York Public Library", ["public", "library"]),
            pytest.param("University of Nebraska", ["university"]),
        ]
    )
    def test_library_keywords(self, search_string, library_keywords):
        """
        GIVEN: An input string
        WHEN:  A LibrarySearchQuery object is instantiated from that search_string
        THEN:  The .library_keywords attribute should be a list of any tokens which match
               a word in LibrarySearchQuery.LIBRARY_KEYWORDS
        """
        sq_obj = LibrarySearchQuery(search_string)
        assert sq_obj.library_keywords == library_keywords

    @pytest.mark.parametrize(
        "search_string,result",
        [
            pytest.param("Alpha    \n Bravo  \t Charlie", "Alpha Bravo Charlie", id="extra_whitespace"),
            pytest.param(
                ("ABCDE " * (math.floor(LibrarySearchQuery.MAX_SEARCH_STRING_LEN / len("ABCDE ")) + 2)).strip(),
                ("ABCDE " * math.floor(LibrarySearchQuery.MAX_SEARCH_STRING_LEN / len("ABCDE "))).strip(),
                id="longer_than_max_len"
            ),
            pytest.param(
                "X" * (LibrarySearchQuery.MAX_SEARCH_STRING_LEN - 2) + ' XXXXX',
                "X" * (LibrarySearchQuery.MAX_SEARCH_STRING_LEN - 2),
                id="partial_token"
            ),
            pytest.param(1234, '', id="numeric_input"),
            pytest.param(["a", "b"], '', id="list_input"),
            pytest.param(None, '', id="none_input"),
        ]
    )
    def test__normalize_search_string(self, search_string, result):
        """
        GIVEN: An input string
        WHEN:  LibrarySearchQuery._normalize_search_string() is called on that string
        THEN:  A string should be returned which meets these criteria:
                * Extraneous whitespace characters converted to single spaces
                * Total length below LibrarySearchQuery.MAX_SEARCH_STRING_LEN
                * If truncating to fewer total characters than MAX_SEARCH_STRING_LEN,
                  the string should not end in a partial word.
        """
        assert LibrarySearchQuery._normalize_search_string(search_string) == result

    @pytest.mark.parametrize(
        "search_string,search_type",
        [
            pytest.param("11212", LibrarySearchQuery.GEOTARGET_SINGLE, id="zipcode_11212"),
        ]
    )
    def test__search_type(self, search_string, search_type):
        sq_obj = LibrarySearchQuery(search_string)
        assert sq_obj._search_type() == search_type
