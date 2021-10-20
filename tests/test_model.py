import datetime
import random

import pytest

from library_registry.config import Configuration
from library_registry.emailer import Emailer
from library_registry.model import (
    Audience,
    CollectionSummary,
    ConfigurationSetting,
    DelegatedPatronIdentifier,
    Hyperlink,
    Library,
    LibraryAlias,
    LibraryType,
    Place,
)
from library_registry.model_helpers import (get_one_or_create)
from library_registry.util import (
    GeometryUtility
)

from . import (
    DatabaseTest,
)


class TestLibrary(DatabaseTest):

    def test_timestamp(self):
        """Timestamp gets automatically set on database commit."""
        nypl = self._library("New York Public Library")
        first_modified = nypl.timestamp
        now = datetime.datetime.utcnow()
        self._db.commit()
        assert (now-first_modified).seconds < 2

        nypl.opds_url = "http://library/"
        self._db.commit()
        assert nypl.timestamp > first_modified

    def test_short_name(self):
        lib = self._library("A Library")
        lib.short_name = 'abcd'
        assert lib.short_name == "ABCD"
        try:
            lib.short_name = 'ab|cd'
            raise Exception("Expected exception not raised.")
        except ValueError as e:
            assert str(e) == 'Short name cannot contain the pipe character.'

    def test_for_short_name(self):
        assert Library.for_short_name(self._db, 'ABCD') is None
        lib = self._library("A Library")
        lib.short_name = 'ABCD'
        assert Library.for_short_name(self._db, 'ABCD') == lib

    def test_for_urn(self):
        assert Library.for_urn(self._db, 'ABCD') is None
        lib = self._library()
        assert Library.for_urn(self._db, lib.internal_urn) == lib

    def test_random_short_name(self):
        # First, try with no duplicate check.
        random.seed(42)
        name = Library.random_short_name()

        expect = 'UDAXIH'
        assert expect == name

        # Reset the random seed so the same name will be generated again.
        random.seed(42)
        # Create a duplicate_check implementation that claims QAHFTR
        # has already been used.
        def already_used(name):
            return name == expect
        name = Library.random_short_name(duplicate_check=already_used)

        # random_short_name now generates `expect`, but it's a
        # duplicate, so it tries again and generates a new string
        # which passes the already_used test.

        expect_next = "HEXDVX"
        assert expect_next == name

        # To avoid an infinite loop, we will stop trying and raise an
        # exception after a certain number of attempts (the default is
        # 20).
        def theyre_all_duplicates(name):
            return True
        with pytest.raises(ValueError) as exc:
            Library.random_short_name(duplicate_check=theyre_all_duplicates)
        assert "Could not generate random short name after 20 attempts!" in str(exc.value)

    def test_set_library_stage(self):
        lib = self._library()

        # We can't change library_stage because only the registry can
        # take a library from production to non-production.
        def crash():
            lib.library_stage = Library.TESTING_STAGE
        with pytest.raises(ValueError) as exc:
            crash()
        assert "This library is already in production" in str(exc.value)

        # Have the registry take the library out of production.
        lib.registry_stage = Library.CANCELLED_STAGE
        assert lib.in_production is False

        # Now we can change the library stage however we want.
        lib.library_stage = Library.TESTING_STAGE
        lib.library_stage = Library.CANCELLED_STAGE
        lib.library_stage = Library.PRODUCTION_STAGE

    def test_in_production(self):
        lib = self._library()

        # The testing code creates a library that starts out in
        # production.
        assert lib.library_stage == Library.PRODUCTION_STAGE
        assert lib.registry_stage == Library.PRODUCTION_STAGE
        assert lib.in_production is True

        # If either library_stage or registry stage is not
        # PRODUCTION_STAGE, we are not in production.
        lib.registry_stage = Library.CANCELLED_STAGE
        assert lib.in_production is False

        lib.library_stage = Library.CANCELLED_STAGE
        assert lib.in_production is False

        lib.registry_stage = Library.PRODUCTION_STAGE
        assert lib.in_production is False

    def test_number_of_patrons(self):
        production_library = self._library()
        assert production_library.number_of_patrons == 0
        identifier1, is_new = DelegatedPatronIdentifier.get_one_or_create(
            self._db, production_library, self._str, DelegatedPatronIdentifier.ADOBE_ACCOUNT_ID,
            None
        )
        assert production_library.number_of_patrons == 1

        # Identifiers for another library don't count towards the total.
        production_library_2 = self._library()
        identifier1, is_new = DelegatedPatronIdentifier.get_one_or_create(
            self._db, production_library_2, self._str, DelegatedPatronIdentifier.ADOBE_ACCOUNT_ID,
            None
        )
        assert production_library.number_of_patrons == 1

        # Identifiers that aren't Adobe Account IDs don't count towards the total.
        identifier2, is_new = DelegatedPatronIdentifier.get_one_or_create(
            self._db, production_library, self._str, "abc", None
        )
        assert production_library.number_of_patrons == 1
        # Identifiers can't be assigned to libraries that aren't in production.
        testing_library = self._library(library_stage=Library.TESTING_STAGE)
        assert testing_library.number_of_patrons == 0
        identifier3, is_new = DelegatedPatronIdentifier.get_one_or_create(
            self._db, testing_library, self._str, DelegatedPatronIdentifier.ADOBE_ACCOUNT_ID,
            None
        )
        assert testing_library.number_of_patrons == 0

        # Using patron_counts_by_library you can determine patron counts for a number
        # of libraries at once.
        counts = Library.patron_counts_by_library(
            self._db, [production_library, production_library_2, testing_library]
        )
        assert counts == {
            production_library.id : 1,
            production_library_2.id : 1,
        }

    def test__feed_restriction(self):
        """Test the _feed_restriction helper method."""

        def feed(production=True):
            """Find only libraries that belong in a certain feed."""
            qu = self._db.query(Library)
            qu = qu.filter(Library._feed_restriction(production))
            return qu.all()

        # This library starts out in production.
        library = self._library()

        # It shows up in both the production and testing feeds.
        for production in (True, False):
            assert feed(production) == [library]

        # Now one party thinks the library is in the testing stage.
        library.registry_stage = Library.TESTING_STAGE

        # It shows up in the testing feed but not the production feed.
        assert feed(True) == []
        assert feed(False) == [library]

        library.library_stage = Library.TESTING_STAGE
        library.registry_stage = Library.PRODUCTION_STAGE
        assert feed(True) == []
        assert feed(False) == [library]

        # Now on party thinks the library is in the cancelled stage,
        # and it will not show up in eithre feed.
        library.library_stage = Library.CANCELLED_STAGE
        for production in (True, False):
            assert feed(production) == []

    def test_set_hyperlink(self):
        library = self._library()

        with pytest.raises(ValueError) as exc:
            library.set_hyperlink("rel")
        assert "No Hyperlink hrefs were specified" in str(exc.value)

        with pytest.raises(ValueError) as exc:
            library.set_hyperlink(None, ["href"])
        assert "No link relation was specified" in str(exc.value)

        link, is_modified = library.set_hyperlink("rel", "href1", "href2")
        assert link.rel == "rel"
        assert link.href == "href1"
        assert is_modified is True

        # Calling set_hyperlink again does not modify the link
        # so long as the old href is still a possibility.
        link2, is_modified = library.set_hyperlink("rel", "href2", "href1")
        assert link2 == link
        assert link2.rel == "rel"
        assert link2.href == "href1"
        assert is_modified is False

        # If there is no way to keep a Hyperlink's href intact,
        # set_hyperlink will modify it.
        link3, is_modified = library.set_hyperlink("rel", "href2", "href3")
        assert link3 == link
        assert link3.rel == "rel"
        assert link3.href == "href2"
        assert is_modified is True

        # Under no circumstances will two hyperlinks for the same rel be
        # created for a given library.
        assert library.hyperlinks == [link3]

        # However, a library can have multiple hyperlinks to the same
        # Resource using different rels.
        link4, modified = library.set_hyperlink("rel2", "href2")
        assert link4.resource == link3.resource
        assert modified is True

        # And two libraries can link to the same Resource using the same
        # rel.
        library2 = self._library()
        link5, modified = library2.set_hyperlink("rel2", "href2")
        assert modified is True
        assert link5.library == library2
        assert link5.resource == link4.resource

    def test_get_hyperlink(self):
        library = self._library()
        link1, is_modified = library.set_hyperlink("contact_email", "contact_href")
        link2, is_modified = library.set_hyperlink("help_email", "help_href")

        contact_link = Library.get_hyperlink(library, "contact_email")
        assert link1 == contact_link

        help_link = Library.get_hyperlink(library, "help_email")
        assert help_link == link2

    def test_library_service_area(self):
        zip = self.zip_10018

        nypl = self._library("New York Public Library", eligibility_areas=[zip])
        [service_area] = nypl.service_areas
        assert service_area.place == zip
        assert service_area.library == nypl

    def test_types(self):
        # Test the various types of libraries.
        # n.b. this incidentally tests Place.library_type.

        postal = self.zip_10018
        city = self.new_york_city
        state = self.new_york_state
        county = self.crude_kings_county
        nation = self._place('CA', 'Canada', Place.NATION, 'CA', None)
        province = self._place("MB", "Manitoba", Place.STATE, "MB", nation)
        everywhere = Place.everywhere(self._db)

        # Libraries with different kinds of service areas are given
        # different types.
        for focus, type in (
            (postal, LibraryType.LOCAL),
            (city, LibraryType.LOCAL),
            (state, LibraryType.STATE),
            (province, LibraryType.PROVINCE),
            (nation, LibraryType.NATIONAL),
            (everywhere, LibraryType.UNIVERSAL)
        ):

            library = self._library(self._str, focus_areas=[focus])
            assert focus.library_type == type
            assert [type] == list(library.types)

        # If a library's service area is ambiguous, it has no service
        # area-related type.
        library = self._library("library", focus_areas=[postal, province])
        assert [] == list(library.types)

    def test_service_area_name(self):

        # Gather a few focus areas; the details don't matter.
        zip = self.zip_10018
        nyc = self.new_york_city
        new_york = self.new_york_state

        # 'Everywhere' is not a place with a distinctive name, so throughout
        # this test it will be ignored.
        everywhere = Place.everywhere(self._db)

        library = self._library(
            "Internet Archive", eligibility_areas=[everywhere],
            focus_areas=[everywhere]
        )
        assert None == library.service_area_name

        # A library with a single eligibility area has a
        # straightforward name.
        library = self._library(
            "test library", eligibility_areas=[everywhere, new_york],
            focus_areas=[everywhere]
        )
        assert "New York" == library.service_area_name

        # If you somehow specify the same place twice, it's fine.
        library = self._library(
            "test library", eligibility_areas=[new_york, new_york],
            focus_areas=[everywhere]
        )
        assert "New York" == library.service_area_name

        # If the library has an eligibility area and a focus area,
        # the focus area takes precedence.
        library = self._library(
            "test library", eligibility_areas=[everywhere, new_york],
            focus_areas=[nyc, everywhere]
        )
        assert "New York, NY" == library.service_area_name

        # If there are multiple focus areas and one eligibility area,
        # we're back to using the focus area.
        library = self._library(
            "test library", eligibility_areas=[everywhere, new_york],
            focus_areas=[nyc, zip, everywhere]
        )
        assert "New York" == library.service_area_name

        # If there are multiple focus areas _and_ multiple eligibility areas,
        # there's no one string that describes the service area.
        library = self._library(
            "test library", eligibility_areas=[everywhere, new_york, zip],
            focus_areas=[nyc, zip, everywhere]
        )
        assert None == library.service_area_name

    def test_nearby(self):
        # Create two libraries. One serves New York City, and one serves
        # the entire state of Connecticut.
        nypl = self._library(
            "New York Public Library", eligibility_areas=[self.new_york_city]
        )
        ct_state = self._library(
            "Connecticut State Library", eligibility_areas=[self.connecticut_state]
        )

        # From this point in Brooklyn, NYPL is the closest library.
        # NYPL's service area includes that point, so the distance is
        # zero. The service area of CT State (i.e. the Connecticut
        # border) is only 44 kilometers away, so it also shows up.
        [(lib1, d1), (lib2, d2)] = Library.nearby(self._db, (40.65, -73.94))

        assert d1 == 0
        assert lib1 == nypl

        assert int(d2/1000) == 44
        assert lib2 == ct_state

        # From this point in Connecticut, CT State is the closest
        # library (0 km away), so it shows up first, but NYPL (61 km
        # away) also shows up as a possibility.
        [(lib1, d1), (lib2, d2)] = Library.nearby(self._db, (41.3, -73.3))
        assert lib1 == ct_state
        assert d1 == 0

        assert lib2 == nypl
        assert int(d2/1000) == 61

        # From this point in Pennsylvania, NYPL shows up (142km away) but
        # CT State does not.
        [(lib1, d1)] = Library.nearby(self._db, (40, -75.8))
        assert lib1 == nypl
        assert int(d1/1000) == 142

        # If we only look within a 100km radius, then there are no
        # libraries near that point in Pennsylvania.
        assert Library.nearby(self._db, (40, -75.8), 100).all() == []

        # By default, nearby() only finds libraries that are in production.
        def m(production):
            return Library.nearby(
                self._db, (41.3, -73.3), production=production
            ).count()
        # Take all the libraries we found earlier out of production.
        for l in ct_state, nypl:
            l.registry_stage = Library.TESTING_STAGE
        # Now there are no results.
        assert m(True) == 0

        # But we can run a search that includes libraries in the TESTING stage.
        assert m(False) == 2

    def test_query_cleanup(self):
        m = Library.query_cleanup

        assert m("THE LIBRARY") == "the library"
        assert m("\tthe   library\n\n") == "the library"
        assert m("the libary") == "the library"

    def test_as_postal_code(self):
        m = Library.as_postal_code
        # US ZIP codes are recognized as postal codes.
        assert m("93203") == "93203"
        assert m("93203-1234") == "93203"
        assert m("the library") is None

        # A UK post code is not currently recognized.
        assert m("AB1 0AA") is None

    def test_query_parts(self):
        m = Library.query_parts
        assert m("93203") == (None, "93203", Place.POSTAL_CODE)
        assert m("new york public library") == ("new york public library", "new york", None)
        assert m("queens library") == ("queens library", "queens", None)
        assert m("kern county library") == ("kern county library", "kern", Place.COUNTY)
        assert m("new york state library") == ("new york state library", "new york", Place.STATE)
        assert m("lapl") == ("lapl", "lapl", None)

    def test_search_by_library_name(self):
        def search(name, here=None, **kwargs):
            return list(
                Library.search_by_library_name(self._db, name, here, **kwargs)
            )

        # The Brooklyn Public Library serves New York City.
        brooklyn = self._library(
            name="Brooklyn Public Library", focus_areas=[self.new_york_city, self.zip_11212]
        )

        # We can find the library by its name.
        assert search("brooklyn public library") == [brooklyn]

        # We can tolerate a small number of typos in a name or alias
        # that is longer than 6 characters.
        assert search("broklyn public library") == [brooklyn]
        get_one_or_create(
            self._db, LibraryAlias, name="Bklynlib", language=None,
            library=brooklyn
        )
        assert search("zklynlib") == [brooklyn]

        # The Boston Public Library serves Boston, MA.
        boston = self._library(
            name="Boston Public Library", focus_areas=[self.boston_ma]
        )

        # Searching for part of the name--i.e. "boston" rather than "boston public library"--should work.
        assert search("boston") == [boston]

        # Both libraries are known colloquially as 'BPL'.
        for library in (brooklyn, boston):
            get_one_or_create(
                self._db, LibraryAlias, name="BPL", language=None,
                library=library
            )
        assert set(search("bpl")) == set([brooklyn, boston]) 
        
        # We do not tolerate typos in short names, because the chance of
        # ambiguity is so high.
        assert search("opl") == []

        # If we're searching for "BPL" from California, Brooklyn shows
        # up first, because it's closer to California.
        assert [x[0].name for x in search("bpl", GeometryUtility.point(35, -118))] == ["Brooklyn Public Library", "Boston Public Library"]

        # If we're searching for "BPL" from Maine, Boston shows
        # up first, because it's closer to Maine.
        assert [x[0].name for x in search("bpl", GeometryUtility.point(43, -70))] == ["Boston Public Library", "Brooklyn Public Library"]

        # By default, search_by_library_name() only finds libraries
        # in production. Put them in the TESTING stage and they disappear.
        for l in (brooklyn, boston):
            l.registry_stage = Library.TESTING_STAGE
        assert search("bpl", production=True) == []

        # But you can find them by passing in production=False.
        assert len(search("bpl", production=False)) == 2

    def test_search_by_location(self):
        # We know about three libraries.
        nypl = self.nypl
        kansas_state = self.kansas_state_library
        connecticut_state = self.connecticut_state_library

        # The NYPL explicitly covers New York City, which has
        # 'Manhattan' as an alias.
        [nyc, zip_11212] = [x.place for x in nypl.service_areas]
        assert "Manhattan" in [x.name for x in nyc.aliases]

        # The Kansas state library covers the entire state,
        # which happens to contain a city called Manhattan.
        [kansas] = [x.place for x in kansas_state.service_areas]
        assert kansas.external_name == "Kansas"
        assert kansas.type == Place.STATE
        manhattan_ks = self.manhattan_ks

        # A search for 'manhattan' finds both libraries.
        libraries = list(Library.search_by_location_name(self._db, "manhattan"))
        assert set([x.name for x in libraries]) == set(["NYPL", "Kansas State Library"])

        # If you're searching from California, the Kansas library
        # shows up first.
        ca_results = Library.search_by_location_name(
            self._db, "manhattan", here=GeometryUtility.point(35, -118)
        )
        assert [x[0].name for x in ca_results] == ["Kansas State Library", "NYPL"]

        # If you're searching from Maine, the New York library shows
        # up first.
        me_results = Library.search_by_location_name(
            self._db, "manhattan", here=GeometryUtility.point(43, -70)
        )
        assert [x[0].name for x in me_results] == ["NYPL", "Kansas State Library"]

        # We can insist that only certain types of places be considered as
        # matching the name. There is no state called 'Manhattan', so
        # this query finds nothing.
        excluded = Library.search_by_location_name(
            self._db, "manhattan", type=Place.STATE
        )
        assert excluded.all() == []

        # A search for "Brooklyn" finds the NYPL, but it only finds it
        # once, even though NYPL is associated with two places called
        # "Brooklyn": New York City and the ZIP code 11212
        [brooklyn_results] = Library.search_by_location_name(
            self._db, "brooklyn", here=GeometryUtility.point(43, -70)
        )
        assert brooklyn_results[0] == nypl

        nypl.registry_stage = Library.TESTING_STAGE
        assert Library.search_by_location_name(self._db, "brooklyn", here=GeometryUtility.point(43, -70), production=True).all() == []
        
        assert Library.search_by_location_name(self._db, "brooklyn", here=GeometryUtility.point(43, -70), production=False).count() == 1
        
    def test_search_within_description(self):
        """Test searching for a phrase within a library's description."""
        library = self._library(
            name="Library With Description",
            description="We are giving this library a description for testing purposes."
        )
        results = list(Library.search_within_description(self._db, "testing purposes"))
        assert results == [library]

    def test_search(self):
        """Test the overall search method."""

        # Here's a Kansas library with a confusing name whose
        # Levenshtein distance from "New York" is 2.
        new_work = self._library(name="Now Work", focus_areas=[self.kansas_state])

        # Here's a library whose service area includes a place called
        # "New York".
        nypl = self.nypl

        libraries = Library.search(self._db, (40.7, -73.9), "NEW YORK")
        # Even though NYPL is closer to the current location, the
        # Kansas library showed up first because it was a name match,
        # as opposed to a service location match.
        assert [x[0].name for x in libraries] == ['Now Work', 'NYPL']
        assert [int(x[1]/1000) for x in libraries] == [1768, 0]

        # This search query has a Levenshtein distance of 1 from "New
        # York", but a distance of 3 from "Now Work", so only NYPL
        # shows up.
        #
        # Although "NEW YORM" matches both the city and state, both of
        # which intersect with NYPL's service area, NYPL only shows up
        # once.
        libraries = Library.search(self._db, (40.7, -73.9), "NEW YORM")
        assert [x[0].name for x in libraries] == ['NYPL']

        # Searching for a place name picks up libraries whose service
        # areas intersect with that place.
        libraries = Library.search(self._db, (40.7, -73.9), "Kansas")
        assert [x[0].name for x in libraries] == ['Now Work']

        # By default, search() only finds libraries in production.
        self.nypl.registry_stage = Library.TESTING_STAGE
        new_work.registry_stage = Library.TESTING_STAGE
        def m(production):
            return len(
                Library.search(
                    self._db, (40.7, -73.9), "New York", production
                )
            )
        assert m(True) == 0

        # But you can find libraries that are in the testing stage
        # by passing in production=False.
        assert m(False) == 2

    def test_search_excludes_duplicates(self):
        # Here's a library that serves a place called Kansas
        # whose name is also "Kansas"
        library = self._library(name="Kansas", focus_areas=[self.kansas_state])
        # It matches both the name search and the location search.
        assert Library.search_by_location_name(self._db, "kansas").all() == [library]
        assert Library.search_by_library_name(self._db, "kansas").all() == [library]

        # But when we do the general search, the library only shows up once.
        [(result, distance)] = Library.search(self._db, (0, 0), "Kansas")
        assert result == library


class TestHyperlink(DatabaseTest):

    def test_notify(self):
        class Mock(Emailer):
            sent = []
            url_for_calls = []

            def __init__(self):
                """We don't need any of the arguments that are required
                for the Emailer constructor.
                """

            def send(self, type, to_address, **kwargs):
                self.sent.append((type, to_address, kwargs))

            def url_for(self, controller, **kwargs):
                """Just a convenient place to mock Flask's url_for()."""
                self.url_for_calls.append((controller, kwargs))
                return "http://url/"

        emailer = Mock()

        ConfigurationSetting.sitewide(
            self._db, Configuration.REGISTRY_CONTACT_EMAIL
        ).value = "me@registry"

        library = self._library()
        library.web_url = "http://library/"
        link, is_modified = library.set_hyperlink(
            Hyperlink.COPYRIGHT_DESIGNATED_AGENT_REL, "mailto:you@library"
        )
        link.notify(emailer, emailer.url_for)

        # A Validation object was created for the Hyperlink.
        validation = link.resource.validation
        secret = validation.secret

        (type, sent_to, kwargs) = emailer.sent.pop()

        # We 'sent' an email about the fact that a new email address was
        # registered.
        assert type == emailer.ADDRESS_NEEDS_CONFIRMATION
        assert sent_to == "you@library"

        # These arguments were created to fill in the ADDRESS_NEEDS_CONFIRMATION
        # template.
        assert kwargs['registry_support'] == "me@registry"
        assert kwargs['email'] == "you@library"
        assert kwargs['rel_desc'] == "copyright designated agent"
        assert kwargs['library'] == library.name
        assert kwargs['library_web_url'] == library.web_url
        assert kwargs['confirmation_link'] == "http://url/"

        # url_for was called to create the confirmation link.
        controller, kwargs = emailer.url_for_calls.pop()
        assert controller == "confirm_resource"
        assert kwargs['secret'] == secret
        assert kwargs['resource_id'] == link.resource.id

        # If a Resource we already know about is associated with
        # a new Hyperlink, an ADDRESS_DESIGNATED email is sent instead.
        link2, is_modified = library.set_hyperlink("help", "mailto:you@library")
        link2.notify(emailer, emailer.url_for)

        (type, href, kwargs) = emailer.sent.pop()
        assert type == emailer.ADDRESS_DESIGNATED
        assert kwargs['rel_desc'] == "patron help contact address"

        # url_for was not called again, since an ADDRESS_DESIGNATED
        # email does not include a validation link.
        assert emailer.url_for_calls == []

        # And the Validation was not reset.
        assert link.resource.validation.secret == secret

        # Same if we somehow send another notification for a Hyperlink with an
        # active Validation.
        link.notify(emailer, emailer.url_for)
        (type, href, kwargs) = emailer.sent.pop()
        assert type == emailer.ADDRESS_DESIGNATED
        assert link.resource.validation.secret == secret

        # However, if a Hyperlink's Validation has expired, it's reset and a new
        # ADDRESS_NEEDS_CONFIRMATION email is sent out.
        now = datetime.datetime.utcnow()
        link.resource.validation.started_at = (now - datetime.timedelta(days=10))
        link.notify(emailer, emailer.url_for)
        (type, href, kwargs) = emailer.sent.pop()
        assert type == emailer.ADDRESS_NEEDS_CONFIRMATION
        assert 'confirmation_link' in kwargs

        # The Validation has been reset.
        assert link.resource.validation == validation
        assert validation.deadline > now
        assert secret != validation.secret


class TestValidation(DatabaseTest):
    """Test the Resource validation process."""

    def test_restart_validation(self):

        # This library has two links.
        library = self._library()
        link1, ignore = library.set_hyperlink("rel", "mailto:me@library.org")
        email = link1.resource
        link2, ignore = library.set_hyperlink("rel", "http://library.org")
        http = link2.resource

        # Let's set up validation for both of them.
        now = datetime.datetime.utcnow()
        email_validation = email.restart_validation()
        http_validation = http.restart_validation()

        for v in (email_validation, http_validation):
            assert (v.started_at - now).total_seconds() < 2
            assert v.secret is not None

        # A random secret was generated for each Validation.
        assert email_validation.secret != http_validation.secret

        # Let's imagine that validation succeeded and is being
        # invalidated for some reason.
        email_validation.success = True
        old_started_at = email_validation.started_at
        old_secret = email_validation.secret
        email_validation_2 = email.restart_validation()

        # Instead of a new Validation being created, the earlier
        # Validation has been invalidated.
        assert email_validation_2 == email_validation
        assert email_validation_2.success is False

        # The secret has changed.
        assert old_secret != email_validation.secret
