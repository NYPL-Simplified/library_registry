import math

import pytest
from util.search import (SIMPLE_POSTCODE_RE, InvalidLSToken,
                         LSBaseTokenClassifier, LSQuery, LSToken, LSTokenSequence)


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
        "tokens,target_list,merged_token_type,max_words,results",
        [
            pytest.param(
                [("alpha", None)],
                ["a target", "another target"],
                LSToken.STATE_NAME,
                3,
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
                3,
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
                3,
                [
                    ("alpha bravo charlie", LSToken.STATE_NAME),
                    ("delta", LSToken.CITY_NAME),
                    ("echo", LSToken.CITY_NAME),
                    ("foxtrot", LSToken.CITY_NAME),
                ],
                id="three_word_match"
            ),
            pytest.param(
                [
                    ("alpha", None),
                    ("bravo", None),
                    ("charlie", None),
                    ("delta", None),
                    ("echo", LSToken.CITY_NAME),
                    ("foxtrot", LSToken.CITY_NAME),
                ],
                ["a target", "another target", "alpha bravo charlie delta", "alpha charlie"],
                LSToken.STATE_NAME,
                3,
                [
                    ("alpha", None),
                    ("bravo", None),
                    ("charlie", None),
                    ("delta", None),
                    ("echo", LSToken.CITY_NAME),
                    ("foxtrot", LSToken.CITY_NAME),
                ],
                id="four_word_match_with_three_word_limit"
            ),
        ]
    )
    def test_merge_multiword_tokens(self, tokens, target_list, merged_token_type, max_words, results):
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
            max_words=max_words
        )
        for n in range(len(results)):
            assert sequence.tokens[n].value == results[n][0]
            assert sequence.tokens[n].type == results[n][1]

    @pytest.mark.parametrize(
        "tokens,results",
        [
            pytest.param(
                [("new", None), ("york", None)],
                [("new york", LSToken.STATE_NAME)],
                id="simple"
            ),
            pytest.param(
                [("alpha", None), ("bravo", None), ("new", None), ("mexico", None), ("charlie", None)],
                [("alpha", None), ("bravo", None), ("new mexico", LSToken.STATE_NAME), ("charlie", None)],
                id="two_word_state_among_unclassified"
            ),
            pytest.param(
                [("01230", LSToken.POSTCODE), ("district", None), ("of", None), ("columbia", None), ("alpha", None)],
                [("01230", LSToken.POSTCODE), ("district of columbia", LSToken.STATE_NAME), ("alpha", None)],
                id="three_word_state_in_partially_classified_group"
            )
        ]
    )
    def test_merge_multiword_statenames(self, tokens, results):
        """
        GIVEN: An instance of LSTokenSequence
        WHEN:  .merge_multiword_statenames() is called on that instance
        THEN:  Sequential, unclassified tokens which comprise a state name should be combined
               into single tokens with the type LSToken.STATE_NAME, and a
               modified copy of the input list returned.
        """
        token_list = [LSToken(x[0], token_type=x[1]) for x in tokens]
        sequence = LSTokenSequence(token_list)
        sequence.merge_multiword_statenames()
        assert len(results) == len(sequence)
        for n in range(len(results)):
            assert sequence.tokens[n].value == results[n][0]
            assert sequence.tokens[n].type == results[n][1]


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
            pytest.param("Alpha", ["alpha"]),
            pytest.param("Alpha Bravo", ["alpha", "bravo"]),
            pytest.param("Alpha, Bravo? Charlie!", ["alpha", "bravo", "charlie"]),
            pytest.param("alpha 12345 54321-3232", ["alpha", "12345", "543213232"])
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
            LSBaseTokenClassifier.classify_tokens(None)

    def test_work_to_do_abstract(self):
        """
        GIVEN: No preconditions
        WHEN:  LSTokenClassifier.work_to_do() is called
        THEN:  A NotImplementedError exception should be raised
        """
        with pytest.raises(NotImplementedError):
            LSBaseTokenClassifier.work_to_do(None)
