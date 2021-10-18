import math

import pytest
from library_registry.util.search import (
    SIMPLE_POSTCODE_RE,
    InvalidLSToken,
    LSBaseTokenClassifier,
    LSCitynameTokenClassifier,
    LSCountynameTokenClassifier,
    LSLibrarynameTokenClassifier,
    LSQuery,
    LSSinglewordTokenClassifier,
    LSStatenameTokenClassifier,
    LSToken,
    LSTokenSequence
)


class TestLSToken:
    def test_string_context(self):
        """
        GIVEN: An LSToken instance
        WHEN:  That instance is evaluated in a string context
        THEN:  The string stored in the instance's .value attribute should be returned
        """
        t_value = "alpha"
        t = LSToken(t_value)
        assert str(t) == t_value
        assert str(t) == t.value

    def test_instance_equality(self):
        """
        GIVEN: Two LSToken instances
        WHEN:  They are compared using the == or != equality comparison operators
        THEN:  True should be returned if they have the same .value attribute
        """
        same_value = "alpha"
        diff_value = "bravo"
        t1 = LSToken(same_value)
        t2 = LSToken(same_value)
        t3 = LSToken(diff_value)

        assert t1 == t2 and id(t1) != id(t2)
        assert t1 != t3

    def test_is_multiword(self):
        """
        GIVEN: An LSToken instance
        WHEN:  That instance's .is_multiword property is accessed
        THEN:  An appropriate boolean value should be returned
        """
        t_single = LSToken("alpha")
        t_multi = LSToken("alpha bravo")
        assert t_single.is_multiword is False
        assert t_multi.is_multiword is True

    def test_type_validation(self):
        """
        GIVEN: A string value and a string type
        WHEN:  An LSToken is instantiated with those values
        THEN:  The .type attribute should be set if it is a valid type
        """
        token_value = "alpha"

        type_valid = LSToken.POSTCODE
        token_one = LSToken(token_value, token_type=type_valid)
        assert token_one.type == type_valid

        type_invalid = "an invalid type"
        token_two = LSToken(token_value, token_type=type_invalid)
        assert token_two.type is None

    @pytest.mark.parametrize(
        "input_value",
        [None, 1, ["alpha", "bravo"], lambda f: f.lower()]
    )
    def test_value_validation(self, input_value):
        """
        GIVEN: No pre-requisites
        WHEN:  An LSToken is instantiated with a non-string value
        THEN:  An InvalidLSToken exception is raised
        """
        with pytest.raises(InvalidLSToken):
            LSToken(input_value)

    @pytest.mark.parametrize(
        "input_string,token_value",
        [
            ("   a   b   ", "a b"),
            (" \n alpha", "alpha"),
            ("bravo     \t\t", "bravo"),
        ]
    )
    def test_value_whitespace_normalization(self, input_string, token_value):
        """
        GIVEN: No pre-requisites
        WHEN:  An LSToken is instantiated with a string containing whitespace
        THEN:  The resulting object's .value should be stripped of leading and trailing
               whitespace characters, and any runs of internal whitespace should be
               reduced to a single space each.
        """
        assert LSToken(input_string).value == token_value


class TestLSTokenSequence:
    def test_create_from_token_objects(self):
        """
        GIVEN: A list of LSToken objects
        WHEN:  Those LSToken objects are used to instantiate an LSTokenSequence
        THEN:  The .tokens attribute of the LSTokenSequence should include the passed objects
        """
        words = ["alpha", "bravo", "charlie", "delta", "echo"]
        token_objects = [LSToken(w) for w in words]
        sequence = LSTokenSequence(token_objects)
        assert sequence.tokens == token_objects

    def test_create_from_strings(self):
        """
        GIVEN: A list of strings
        WHEN:  Those strings are used to instantiate an LSTokenSequence
        THEN:  The .tokens attribute of the LSTokenSequence should be a list of LSToken objects
               created from the strings passed in.
        """
        words = ["alpha", "bravo", "charlie", "delta", "echo"]
        token_objects = [LSToken(w) for w in words]
        sequence = LSTokenSequence(words)
        assert sequence.tokens == token_objects

    def test_string_context(self):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That instance is evaluated in a string context
        THEN:  A space-separated string of its component tokens should result
        """
        words = ["alpha", "bravo", "charlie", "delta", "echo"]
        token_objects = [LSToken(w) for w in words]
        sequence = LSTokenSequence(token_objects)
        assert str(sequence) == " ".join(words)

    def test_length_context(self):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That instance is passed to the len() built-in
        THEN:  The return value should represent the number of values in the .tokens list attribute
        """
        words = ["alpha", "bravo", "charlie", "delta", "echo"]
        token_objects = [LSToken(w) for w in words]
        sequence = LSTokenSequence(token_objects)
        assert len(sequence) == len(words)

    def test_iterable_context(self):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is accessed in an iterable context
        THEN:  The items in .tokens should iteratively yield
        """
        tokens = [LSToken('alpha'), LSToken('bravo'), LSToken('charlie')]
        sequence = LSTokenSequence(tokens)
        assert list(sequence) == tokens

        for idx, token in enumerate(sequence):
            assert token == tokens[idx]

    @pytest.mark.parametrize(
        "input_tokens,result",
        [
            pytest.param(
                [
                    ("Alabama", LSToken.STATE_NAME),
                    ("Nevada", LSToken.STATE_NAME),
                    ("Michigan", LSToken.STATE_NAME),
                ],
                True,
                id="three_classified_tokens"
            ),
            pytest.param(
                [
                    ("alpha", None),
                    ("bravo", None),
                    ("charlie", None),
                ],
                False,
                id="three_unclassified_tokens"
            ),
            pytest.param(
                [
                    ("alpha", None),
                    ("Nevada", LSToken.STATE_NAME),
                    ("bravo", None),
                ],
                False,
                id="mixed_classified_and_unclassified"
            ),
        ]
    )
    def test_all_classified_property(self, input_tokens, result):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  The .all_classified property of that instance is evaluated
        THEN:  If all LSTokens in .tokens already have a .type, return True, else False
        """
        token_objects = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_objects)
        assert sequence.all_classified == result

    @pytest.mark.parametrize(
        "input_tokens,result",
        [
            pytest.param(
                [
                    ("Alabama", LSToken.STATE_NAME),
                    ("Nevada", LSToken.STATE_NAME),
                    ("Michigan", LSToken.STATE_NAME),
                ],
                0,
                id="three_classified_tokens"
            ),
            pytest.param(
                [
                    ("alpha", None),
                    ("bravo", None),
                    ("charlie", None),
                ],
                3,
                id="three_unclassified_tokens"
            ),
            pytest.param(
                [
                    ("alpha", None),
                    ("Nevada", LSToken.STATE_NAME),
                    ("bravo", None),
                ],
                2,
                id="mixed_classified_and_unclassified"
            ),
        ]
    )
    def test_unclassified_count_property(self, input_tokens, result):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  The .unclassified_count property of that instance is evaluated
        THEN:  An integer representing the number of unclassified tokens in .tokens should be returned
        """
        token_objects = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_objects)
        assert sequence.unclassified_count == result

    @pytest.mark.parametrize(
        "input_items,expected_max_run",
        [
            pytest.param(
                [
                    ("alpha", LSToken.CITY_NAME),
                    ("bravo", None),
                    ("charlie", None),
                    ("delta", LSToken.CITY_NAME),
                    ("echo", LSToken.CITY_NAME),
                    ("foxtrot", None),
                    ("golf", None),
                    ("hotel", None),
                    ("india", None),
                    ("juliet", LSToken.CITY_NAME),
                ],
                4,
                id="max_run_of_four"
            ),
            pytest.param([("alpha", None)], 1, id="single_item"),
            pytest.param(
                [
                    ("alpha", LSToken.CITY_NAME),
                    ("bravo", LSToken.CITY_NAME),
                    ("charlie", LSToken.CITY_NAME),
                    ("delta", LSToken.CITY_NAME),
                    ("echo", LSToken.CITY_NAME),
                ],
                0,
                id="zero_runs"
            )
        ]
    )
    def test_longest_unclassified_run_property(self, input_items, expected_max_run):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  The .longest_unclassified_run property is accessed
        THEN:  An integer should be returned representing the longest consecutive sequence
               of tokens in that list whose .type attributes evaluate to None.
        """
        tokens = [LSToken(x[0], token_type=x[1]) for x in input_items]
        sequence = LSTokenSequence(tokens)
        assert sequence.longest_unclassified_run == expected_max_run

    @pytest.mark.parametrize(
        "tokens,target_list,merged_token_type,results",
        [
            pytest.param(
                [("alpha", None)],
                ["a target", "another target"],
                LSToken.STATE_NAME,
                [("alpha", None)],
                id="single_token_unclassified"
            ),
            pytest.param(
                [
                    ("alpha", None),
                    ("bravo", None),
                    ("charlie", None),
                    ("delta", LSToken.CITY_NAME),
                    ("echo", LSToken.CITY_NAME),
                    ("foxtrot", LSToken.CITY_NAME),
                ],
                ["a target", "another target", "bravo charlie", "alpha charlie"],
                LSToken.STATE_NAME,
                [
                    ("alpha", None),
                    ("bravo charlie", LSToken.STATE_NAME),
                    ("delta", LSToken.CITY_NAME),
                    ("echo", LSToken.CITY_NAME),
                    ("foxtrot", LSToken.CITY_NAME),
                ],
                id="two_word_match"
            ),
            pytest.param(
                [
                    ("alpha", None),
                    ("bravo", None),
                    ("charlie", None),
                    ("delta", LSToken.CITY_NAME),
                    ("echo", LSToken.CITY_NAME),
                    ("foxtrot", LSToken.CITY_NAME),
                ],
                ["a target", "another target", "alpha bravo charlie", "alpha charlie"],
                LSToken.STATE_NAME,
                [
                    ("alpha bravo charlie", LSToken.STATE_NAME),
                    ("delta", LSToken.CITY_NAME),
                    ("echo", LSToken.CITY_NAME),
                    ("foxtrot", LSToken.CITY_NAME),
                ],
                id="three_word_match"
            ),
            pytest.param(
                [("memorial", LSToken.LIBRARY_KEYWORD), ("library", LSToken.LIBRARY_KEYWORD)],
                ["memorial library"],
                LSToken.LIBRARY_NAME,
                [("memorial library", LSToken.LIBRARY_NAME)],
                id="merge_preclassified_tokens"
            ),
            pytest.param(
                [("alpha", None), ("bravo", None), ("charlie", None),
                 ("delta", None), ("echo", None), ("foxtrot", None)],
                ["alpha bravo", "bravo charlie delta echo"],
                LSToken.LIBRARY_NAME,
                [("alpha", None), ("bravo charlie delta echo", LSToken.LIBRARY_NAME), ("foxtrot", None)],
                id="longer_target_should_take_precedence"
            ),
            pytest.param(
                [("alpha bravo", None), ("charlie delta", None), ("echo", None), ("foxtrot", None)],
                ["bravo charlie", "echo foxtrot"],
                LSToken.LIBRARY_NAME,
                [("alpha bravo", None), ("charlie delta", None), ("echo foxtrot", LSToken.LIBRARY_NAME)],
                id="dont_merge_partial_tokens"
            ),
            pytest.param(
                [(x, None) for x in "los angeles los alamos los gordos 12345".split()],
                ["los angeles", "los gordos", "los alamos", "chesterfield"],
                LSToken.CITY_NAME,
                [
                    ("los angeles", LSToken.CITY_NAME),
                    ("los alamos", LSToken.CITY_NAME),
                    ("los gordos", LSToken.CITY_NAME),
                    ("12345", None)
                ],
                id="multiple_matching_patterns"
            ),
        ]
    )
    def test_merge_multiword_tokens(self, tokens, target_list, merged_token_type, results):
        """
        GIVEN:
        WHEN:
        THEN:
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in tokens]
        sequence = LSTokenSequence(token_list)
        sequence.merge_multiword_tokens(
            target_list=target_list,
            merged_token_type=merged_token_type,
        )

        for n in range(len(results)):
            assert sequence.tokens[n].value == results[n][0]
            assert sequence.tokens[n].type == results[n][1]

    @pytest.mark.parametrize(
        "tokens,input_targets,output_targets",
        [
            pytest.param(
                [("alpha", None), ("bravo", None)],
                ["alpha bravo", "bravo charlie"],
                ["alpha bravo"],
                id="single_match"
            ),
            pytest.param(
                [("alpha", None), ("bravo", None), ("charlie", None)],
                ["alpha bravo", "bravo charlie"],
                ["alpha bravo", "bravo charlie"],
                id="double_match"
            ),
            pytest.param(
                [("alpha", None), ("bravo", None), ("charlie", None)],
                ["alpha bravo", "bravo charlie", "alpha bravo", "charlie delta"],
                ["alpha bravo", "bravo charlie"],
                id="double_match_with_duplicate_and_missing"
            ),
            pytest.param(
                [("alpha bravo charlie delta", LSToken.POSTCODE)],
                ["alpha bravo"],
                ["alpha bravo"],
                id="single_match_on_multiword_token_in_sequence"
            ),
            pytest.param(
                [("a b c d e f g h", None)],
                ["a b", "a b c d e f g h"],
                ["a b"],
                id="max_words_exceeds_global_limit"
            ),
            pytest.param(
                [("alpha bravo", None), ("charlie", None), ("delta", None)],
                ["alpha bravo", "bravo charlie"],
                ["alpha bravo"],
                id="target_breaks_token_boundaries"
            ),
        ]
    )
    def test__multiword_targets_found_in_sequence(self, tokens, input_targets, output_targets):
        """
        GIVEN: An LSTokenSequence instance and a list of multi-word targets
        WHEN:  The ._multiword_targets_found_in_sequence() method of the token sequence is called
        THEN:  The set of strings found
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in tokens]
        sequence = LSTokenSequence(token_list)
        actual = sequence._multiword_targets_found_in_sequence(input_targets)
        for (idx, target) in enumerate(sorted(actual)):
            assert target == sorted(output_targets)[idx]

    @pytest.mark.parametrize(
        "input_targets,output_targets",
        [
            pytest.param(
                ["a  string \n with   weird spacing", "a normally spaced string"],
                ["a string with weird spacing", "a normally spaced string"],
                id="whitespace_anomalies"
            ),
            pytest.param(
                ["A stRING", "ANOTHER STRING"],
                ["a string", "another string"],
                id="capitalization_anomalies"
            ),
        ]
    )
    def test__normalize_target_list(self, input_targets, output_targets):
        actual = LSTokenSequence._normalize_target_list(input_targets)
        assert actual == output_targets


class TestLSQuery:
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
        WHEN:  That string is matched against LSQuery.SIMPLE_POSTCODE_RE
        THEN:  If the string is a 5 digit or 9 digit number, a match should return
        """
        assert bool(SIMPLE_POSTCODE_RE.match(input_string)) is result

    def test_boolean_context(self):
        """
        GIVEN: A search_string that is None or not a string
        WHEN:  An attempt is made to instantiate a LSQuery object based on that search_string
        THEN:  The returned object should evaluate as False in a boolean context
        """
        assert not LSQuery(None)
        assert not LSQuery(12345)
        assert not LSQuery([1, 2, 3])
        assert not LSQuery({"a": 1})
        assert not LSQuery((1, 2, 3))

    @pytest.mark.parametrize(
        "search_string,tokens",
        [
            pytest.param("Alpha", ["alpha"], id="single_word"),
            pytest.param("Alpha Bravo", ["alpha", "bravo"], id="two_words"),
            pytest.param("Alpha, Bravo? Charlie!", ["alpha", "bravo", "charlie"], id="three_words_with_punctuation"),
            pytest.param("alpha 12345 54321-3232", ["alpha", "12345", "543213232"], id="words_and_numbers"),
        ]
    )
    def test_tokenize(self, search_string, tokens):
        """
        GIVEN: A search_string
        WHEN:  A LSQuery object is instantiated from that search_string
        THEN:  The following should be true:
                * The .raw_string attribute should match the input string
                * The .raw_tokens attribute should be a list of the space separated items in the input
                * The .tokens attribute should be a list of the space separated items, less punctuation, lowercased
        """
        sq_obj = LSQuery(search_string)
        assert sq_obj.raw_string == search_string[:(LSQuery.MAX_SEARCH_STRING_LEN * 3)]
        assert sq_obj.tokens == [LSToken(t) for t in tokens]

    @pytest.mark.parametrize(
        "search_string,result",
        [
            pytest.param("Alpha    \n Bravo  \t Charlie", "Alpha Bravo Charlie", id="extra_whitespace"),
            pytest.param(
                ("ABCDE " * (math.floor(LSQuery.MAX_SEARCH_STRING_LEN / len("ABCDE ")) + 2)).strip(),
                ("ABCDE " * math.floor(LSQuery.MAX_SEARCH_STRING_LEN / len("ABCDE "))).strip(),
                id="longer_than_max_len"
            ),
            pytest.param(
                "X" * (LSQuery.MAX_SEARCH_STRING_LEN - 2) + ' XXXXX',
                "X" * (LSQuery.MAX_SEARCH_STRING_LEN - 2),
                id="partial_token"
            ),
            pytest.param("Jonestown Memorial Libary", "Jonestown Memorial library", id="common_mistake"),
            pytest.param(1234, '', id="numeric_input"),
            pytest.param(["a", "b"], '', id="list_input"),
            pytest.param(None, '', id="none_input"),
        ]
    )
    def test__normalize_search_string(self, search_string, result):
        """
        GIVEN: An input string
        WHEN:  LSQuery._normalize_search_string() is called on that string
        THEN:  A string should be returned which meets these criteria:
                * Extraneous whitespace characters converted to single spaces
                * Total length below LSQuery.MAX_SEARCH_STRING_LEN
                * If truncating to fewer total characters than MAX_SEARCH_STRING_LEN,
                  the string should not end in a partial word.
        """
        assert LSQuery._normalize_search_string(search_string) == result

    @pytest.mark.skip
    @pytest.mark.parametrize(
        "search_string,search_type",
        [
            pytest.param("11212", LSQuery.GEOTARGET_SINGLE, id="zipcode_11212"),
        ]
    )
    def test__search_type(self, search_string, search_type):
        sq_obj = LSQuery(search_string)
        assert sq_obj._search_type() == search_type


class TestLSBaseTokenClassifier:
    def test_classify_tokens_abstract(self):
        """
        GIVEN: No preconditions
        WHEN:  LSTokenClassifier.classify_tokens() is called
        THEN:  A NotImplementedError exception should be raised
        """
        with pytest.raises(NotImplementedError):
            LSBaseTokenClassifier.classify(None)

    @pytest.mark.parametrize(
        "tokens,result",
        [
            pytest.param([("new", None), ("york", None)], True, id="not_all_classified"),
            pytest.param([("new york", LSToken.STATE_NAME)], False, id="all_classified"),
        ]
    )
    def test_work_to_do(self, tokens, result):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSBaseTokenClassifier.work_to_do()
        THEN:  A boolean value representing whether all tokens are already classified should return
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in tokens]
        sequence = LSTokenSequence(token_list)
        assert LSBaseTokenClassifier.work_to_do(sequence) is result


class TestLSSinglewordTokenClassifier:
    @pytest.mark.parametrize(
        "input_tokens,output_tokens",
        [
            pytest.param(
                [("12345", LSToken.STATE_ABBR)],
                [("12345", LSToken.STATE_ABBR)],
                id="dont_change_already_classified_tokens"
            ),
            pytest.param(
                [("carson city nv", None)],
                [("carson city nv", None)],
                id="dont_change_multiword_tokens"
            ),
            pytest.param(
                [("carson", None), ("city", None), ("89403", None)],
                [("carson", None), ("city", None), ("89403", LSToken.POSTCODE)],
                id="postcode"
            ),
            pytest.param(
                [("carson", None), ("city", None), ("nv", None)],
                [("carson", None), ("city", None), ("nv", LSToken.STATE_ABBR)],
                id="state_abbreviation"
            ),
            pytest.param(
                [("carson", None), ("city", None), ("nevada", None)],
                [("carson", None), ("city", None), ("nevada", LSToken.STATE_NAME)],
                id="state_name"
            ),
            pytest.param(
                [("library", None), ("of congress", None)],
                [("library", LSToken.LIBRARY_KEYWORD), ("of congress", None)],
                id="library_keyword"
            ),
            pytest.param(
                [("library", None), ("of", None), ("nevada", None), ("apple", None)],
                [("library", LSToken.LIBRARY_KEYWORD), ("of", None), ("nevada", LSToken.STATE_NAME), ("apple", None)],
                id="multiple_classifiable_tokens"
            )
        ]
    )
    def test_classify(self, input_tokens, output_tokens):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSSinglewordTokenClassifier.classify()
        THEN:  The returned sequence should have appropriate classifications performed
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_list)
        results = LSSinglewordTokenClassifier.classify(sequence)
        for idx, token in enumerate(results.tokens):
            assert token.value == output_tokens[idx][0]
            assert token.type == output_tokens[idx][1]


class TestLSStatenameTokenClassifier:
    @pytest.mark.parametrize(
        "input_tokens,output_tokens",
        [
            pytest.param(
                [("carson", None), ("city", None)],
                [("carson", None), ("city", None)],
                id="no_state_names"
            ),
            pytest.param(
                [("carson", None), ("city", None), ("nevada", None)],
                [("carson", None), ("city", None), ("nevada", LSToken.STATE_NAME)],
                id="single_word_state_name"
            ),
            pytest.param(
                [("new", None), ("paltz", None), ("new", None), ("york", None)],
                [("new", None), ("paltz", None), ("new york", LSToken.STATE_NAME)],
                id="multi_word_state_name"
            )
        ]
    )
    def test_classify(self, input_tokens, output_tokens):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSStatenameTokenClassifier.classify()
        THEN:  The returned sequence should have appropriate classifications performed
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_list)
        results = LSStatenameTokenClassifier.classify(sequence)
        for idx, token in enumerate(results.tokens):
            assert token.value == output_tokens[idx][0]
            assert token.type == output_tokens[idx][1]


class TestLSCitynameTokenClassifier:
    @pytest.mark.parametrize(
        "input_tokens,result",
        [
            pytest.param([("alpha", None)], False, id="single_token_sequence"),
            pytest.param([("alpha", LSToken.POSTCODE), ("bravo", LSToken.POSTCODE)], False, id="already_classified"),
            pytest.param([("alpha", None), ("city", None), ("nebraska", None)], True, id="city_bareword"),
            pytest.param([("alpha", None), ("tn", LSToken.STATE_ABBR)], True, id="state_abbr"),
            pytest.param([("alpha", None), ("maine", LSToken.STATE_NAME)], True, id="state_name"),
            pytest.param([("a", None), ("b", None), ("c", None)], False, id="no_cityword_or_state_types"),
        ]
    )
    def test_work_to_do(self, input_tokens, result):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSCitynameTokenClassifier.work_to_do()
        THEN:  A boolean representing whether there is potential classification work should be returned
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_list)
        assert LSCitynameTokenClassifier.work_to_do(sequence) is result

    @pytest.mark.parametrize(
        "input_tokens,output_tokens",
        [
            pytest.param(
                [("city", None), ("of", None), ("12345", LSToken.POSTCODE)],
                [("city", None), ("of", None), ("12345", LSToken.POSTCODE)],
                id="barewords_city_of_no_work_to_do"
            ),
            pytest.param(
                [("city", None), ("of", None), ("industry", None)],
                [("city of industry", LSToken.CITY_NAME)],
                id="barewords_city_of"
            ),
            pytest.param(
                [("city", None), ("of", None), ("industry", None), ("anotherword", None)],
                [("city of industry anotherword", LSToken.CITY_NAME)],
                id="barewords_city_of"
            ),
            pytest.param(
                [("city", None), ("of", None), ("industry", None), ("ca", LSToken.STATE_ABBR)],
                [("city of industry", LSToken.CITY_NAME), ("ca", LSToken.STATE_ABBR)],
                id="barewords_city_of_with_state_token_following"
            ),
            pytest.param(
                [("city", None), ("hall", None), ("ca", LSToken.STATE_ABBR)],
                [("city", None), ("hall", None), ("ca", LSToken.STATE_ABBR)],
                id="city_bareword_is_first_no_work_to_do"
            ),
            pytest.param(
                [("paradise", None), ("city", None)],
                [("paradise city", LSToken.CITY_NAME)],
                id="city_bareword_single_word_precedes"
            ),
            pytest.param(
                [("wonderful", None), ("multiword", None), ("paradise", None), ("city", None)],
                [("wonderful multiword paradise city", LSToken.CITY_NAME)],
                id="city_bareword_multiple_words_precede"
            ),
            pytest.param(
                [("12345", LSToken.POSTCODE), ("city", None)],
                [("12345", LSToken.POSTCODE), ("city", None)],
                id="city_bareword_preceded_by_already_classified"
            ),
            pytest.param(
                [("yreka", None), ("ca", LSToken.STATE_ABBR)],
                [("yreka", LSToken.CITY_NAME), ("ca", LSToken.STATE_ABBR)],
                id="one_word_city_followed_by_state_abbr"
            ),
            pytest.param(
                [("yreka", None), ("california", LSToken.STATE_NAME)],
                [("yreka", LSToken.CITY_NAME), ("california", LSToken.STATE_NAME)],
                id="one_word_city_followed_by_state_name"
            ),
            pytest.param(
                [("12345", LSToken.POSTCODE), ("los", None), ("angeles", None), ("ca", LSToken.STATE_ABBR)],
                [("12345", LSToken.POSTCODE), ("los angeles", LSToken.CITY_NAME), ("ca", LSToken.STATE_ABBR)],
                id="city_name_in_middle_of_sequence"
            ),
        ]
    )
    def test_classify(self, input_tokens, output_tokens):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSCitynameTokenClassifier.classify()
        THEN:  The returned sequence should have appropriate classifications performed
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_list)
        results = LSCitynameTokenClassifier.classify(sequence)
        for idx, token in enumerate(results.tokens):
            assert token.value == output_tokens[idx][0]
            assert token.type == output_tokens[idx][1]


class TestLSCountynameTokenClassifier:
    @pytest.mark.parametrize(
        "input_tokens,result",
        [
            pytest.param(
                [("natchitoches", None), ("LA", LSToken.STATE_ABBR)], False,
                id="no_county_words_present"
            ),
            pytest.param(
                [("natchitoches", None), ("parish", None), ("LA", LSToken.STATE_ABBR)], True,
                id="parish_countyword_present"
            ),
            pytest.param(
                [("dekalb", None), ("county", None), ("GA", LSToken.STATE_ABBR)], True,
                id="county_countyword_present"
            ),
        ]
    )
    def test_work_to_do(self, input_tokens, result):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSCountynameTokenClassifier.work_to_do()
        THEN:  A boolean representing whether there is potential classification work should be returned
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_list)
        assert LSCountynameTokenClassifier.work_to_do(sequence) is result

    @pytest.mark.parametrize(
        "input_tokens,output_tokens",
        [
            pytest.param(
                [("dekalb", None), ("county", None)],
                [("dekalb county", LSToken.COUNTY_NAME)],
                id="dekalb_county"
            ),
            pytest.param(
                [("natchitoches", None), ("parish", None)],
                [("natchitoches parish", LSToken.COUNTY_NAME)],
                id="natchitoches_parish"
            ),
            pytest.param(
                [("dekalb", None), ("county", None), ("GA", LSToken.STATE_ABBR)],
                [("dekalb county", LSToken.COUNTY_NAME), ("GA", LSToken.STATE_ABBR)],
                id="dekalb_county_ga"
            ),
            pytest.param(
                [("12345", LSToken.POSTCODE), ("dekalb", None), ("county", None), ("GA", LSToken.STATE_ABBR)],
                [("12345", LSToken.POSTCODE), ("dekalb county", LSToken.COUNTY_NAME), ("GA", LSToken.STATE_ABBR)],
                id="dekalb_county_ga_leading_postcode"
            ),
            pytest.param(
                [("alpha", None), ("bravo", None), ("county", None)],
                [("alpha bravo county", LSToken.COUNTY_NAME)],
                id="two_word_county_name"
            ),
            pytest.param(
                [("alpha", None), ("bravo", None), ("charlie", None), ("county", None)],
                [("alpha bravo charlie county", LSToken.COUNTY_NAME)],
                id="three_word_county_name"
            ),
        ]
    )
    def test_classify(self, input_tokens, output_tokens):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSCountynameTokenClassifier.classify()
        THEN:  The returned sequence should have appropriate classifications performed
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_list)
        results = LSCountynameTokenClassifier.classify(sequence)
        for idx, token in enumerate(results.tokens):
            assert token.value == output_tokens[idx][0]
            assert token.type == output_tokens[idx][1]


class TestLSLibrarynameTokenClassifier:
    @pytest.mark.parametrize(
        "input_tokens,result",
        [
            pytest.param(
                [("alpha", None), ("bravo", None), ("charlie", None)], False,
                id="no_library_keywords"
            ),
            pytest.param(
                [("alpha", None), ("library", None), ("charlie", None)], True,
                id="one_library_keyword"
            ),
            pytest.param(
                [("archive", None), ("library", None), ("charlie", None)], True,
                id="two_library_keywords"
            ),
            pytest.param(
                [("archive", LSToken.LIBRARY_KEYWORD), ("library", LSToken.LIBRARY_KEYWORD), ("charlie", None)], True,
                id="two_library_keywords_preclassified"
            ),
            pytest.param(
                [("something", LSToken.LIBRARY_KEYWORD), ("alpha", None)], True,
                id="classified_keyword_not_in_library_keyword_list"
            ),
        ]
    )
    def test_work_to_do(self, input_tokens, result):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSLibrarynameTokenClassifier.work_to_do()
        THEN:  A boolean representing whether there is potential classification work should be returned
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_list)
        assert LSLibrarynameTokenClassifier.work_to_do(sequence) is result

    @pytest.mark.parametrize(
        "input_tokens,output_tokens",
        [
            pytest.param(
                [("alpha", None), ("library", LSToken.LIBRARY_KEYWORD)],
                [("alpha library", LSToken.LIBRARY_NAME)],
                id="simple_library_name"
            ),
        ]
    )
    def test_classify(self, input_tokens, output_tokens):
        """
        GIVEN: An LSTokenSequence instance
        WHEN:  That sequence is passed to LSLibrarynameTokenClassifier.classify()
        THEN:  The returned sequence should have appropriate classifications performed
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in input_tokens]
        sequence = LSTokenSequence(token_list)
        results = LSLibrarynameTokenClassifier.classify(sequence)
        for idx, token in enumerate(results.tokens):
            assert token.value == output_tokens[idx][0]
            assert token.type == output_tokens[idx][1]
