# encoding: utf-8
import pytest

from util.language import LanguageCodes

def eq_(a, b):
    assert a == b


class TestLanguageCodes(object):

    def test_lookups(self):
        c = LanguageCodes
        eq_("eng", c.two_to_three['en'])
        eq_("en", c.three_to_two['eng'])
        eq_(["English"], c.english_names['en'])
        eq_(["English"], c.english_names['eng'])
        eq_(["English"], c.native_names['en'])
        eq_(["English"], c.native_names['eng'])

        eq_("spa", c.two_to_three['es'])
        eq_("es", c.three_to_two['spa'])
        eq_(['Spanish', 'Castilian'], c.english_names['es'])
        eq_(['Spanish', 'Castilian'], c.english_names['spa'])
        eq_(["español", "castellano"], c.native_names['es'])
        eq_(["español", "castellano"], c.native_names['spa'])

        eq_("chi", c.two_to_three['zh'])
        eq_("zh", c.three_to_two['chi'])
        eq_(["Chinese"], c.english_names['zh'])
        eq_(["Chinese"], c.english_names['chi'])
        # We don't have this translation yet.
        eq_([], c.native_names['zh'])
        eq_([], c.native_names['chi'])

        assert c.two_to_three['nosuchlanguage'] is None
        assert c.three_to_two['nosuchlanguage'] is None
        eq_([], c.english_names['nosuchlanguage'])
        eq_([], c.native_names['nosuchlanguage'])

    def test_locale(self):
        m = LanguageCodes.iso_639_2_for_locale
        eq_("eng", m("en-US"))
        eq_("eng", m("en"))
        eq_("eng", m("en-GB"))
        assert m("nq-none") is None

    def test_string_to_alpha_3(self):
        m = LanguageCodes.string_to_alpha_3
        eq_("eng", m("en"))
        eq_("eng", m("eng"))
        eq_("eng", m("en-GB"))
        eq_("eng", m("English"))
        eq_("eng", m("ENGLISH"))
        eq_("ssa", m("Nilo-Saharan languages"))
        assert m("NO SUCH LANGUAGE") is None

    def test_name_for_languageset(self):
        m = LanguageCodes.name_for_languageset
        eq_("", m([]))
        eq_("English", m(["en"]))
        eq_("English", m(["eng"]))
        eq_("español", m(['es']))
        eq_("English/español", m(["eng", "spa"]))
        eq_("español/English", m("spa,eng"))
        eq_("español/English/Chinese", m(["spa","eng","chi"]))
        with pytest.raises(ValueError):
            m(["eng, nxx"])
