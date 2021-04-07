import random
import uuid

import pytest

from library_registry.model import (
    Audience,
    CollectionSummary,
    DelegatedPatronIdentifier,
    Library,
    Place,
)


class TestLibrary:
    def test_short_name_validation(self, db_session, create_test_library):
        lib = create_test_library(db_session)
        lib.short_name = "abcd"
        assert lib.short_name == "ABCD"
        with pytest.raises(ValueError) as exc:
            lib.short_name = "ab|cd"
        assert "Short name cannot contain the pipe character" in str(exc.value)

    def test_for_short_name(self, db_session, create_test_library):
        assert Library.for_short_name(db_session, 'ABCD') is None
        lib = create_test_library(db_session, library_name="A Library")
        lib.short_name = 'ABCD'
        assert Library.for_short_name(db_session, 'ABCD') == lib

    def test_for_urn(self, db_session, create_test_library):
        assert Library.for_urn(db_session, 'ABCD') is None
        lib = create_test_library(db_session)
        assert Library.for_urn(db_session, lib.internal_urn) == lib

    def test_random_short_name(self):
        # First, try with no duplicate check.
        random.seed(42)
        expect = 'UDAXIH'
        assert Library.random_short_name() == expect

        # Reset the random seed so the same name will be generated again.
        random.seed(42)

        # Create a duplicate_check implementation that claims UDAXIH has already been used.
        def already_used(name):
            return name == expect
        name = Library.random_short_name(duplicate_check=already_used)

        # random_short_name now generates `expect`, but it's a
        # duplicate, so it tries again and generates a new string
        # which passes the already_used test.
        expect_next = "HEXDVX"
        assert name == expect_next

        # To avoid an infinite loop, we will stop trying and raise an
        # exception after a certain number of attempts (the default is 20).
        def theyre_all_duplicates(name):
            return True

        with pytest.raises(ValueError) as exc:
            Library.random_short_name(duplicate_check=theyre_all_duplicates)
        assert "Could not generate random short name after 20 attempts!" in str(exc.value)

    def test_set_library_stage(self, db_session, create_test_library):
        lib = create_test_library(db_session)

        # We can't change library_stage because only the registry can
        # take a library from production to non-production.
        with pytest.raises(ValueError) as exc:
            lib.library_stage = Library.TESTING_STAGE
        assert "This library is already in production" in str(exc.value)

        # Have the registry take the library out of production.
        lib.registry_stage = Library.CANCELLED_STAGE
        assert lib.in_production is False

        # Now we can change the library stage however we want.
        lib.library_stage = Library.TESTING_STAGE
        lib.library_stage = Library.CANCELLED_STAGE
        lib.library_stage = Library.PRODUCTION_STAGE

    def test_in_production(self, db_session, create_test_library):
        lib = create_test_library(db_session)

        # The testing code creates a library that starts out in production.
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

    def test_number_of_patrons(self, db_session, create_test_library):
        production_library = create_test_library(db_session)
        assert production_library.number_of_patrons == 0
        (identifier1, _) = DelegatedPatronIdentifier.get_one_or_create(
            db_session, production_library, str(uuid.uuid4()), DelegatedPatronIdentifier.ADOBE_ACCOUNT_ID, None
        )
        assert production_library.number_of_patrons == 1

        # Identifiers that aren't Adobe Account IDs don't count towards the total.
        (identifier2, _) = DelegatedPatronIdentifier.get_one_or_create(
            db_session, production_library, str(uuid.uuid4()), "abc", None
        )
        assert production_library.number_of_patrons == 1

        # Identifiers can't be assigned to libraries that aren't in production.
        testing_library = create_test_library(db_session, library_stage=Library.TESTING_STAGE)
        assert testing_library.number_of_patrons == 0
        (identifier3, _) = DelegatedPatronIdentifier.get_one_or_create(
            db_session, testing_library, str(uuid.uuid4()), DelegatedPatronIdentifier.ADOBE_ACCOUNT_ID, None
        )
        assert testing_library.number_of_patrons == 0

    def test__feed_restriction(self, db_session, create_test_library):
        """Test the _feed_restriction helper method."""

        def feed(db_session, production=True):
            """Find only libraries that belong in a certain feed."""
            qu = db_session.query(Library)
            qu = qu.filter(Library._feed_restriction(production))
            return qu.all()

        # This library starts out in production.
        library = create_test_library(db_session)

        # It shows up in both the production and testing feeds.
        for production in (True, False):
            assert feed(db_session, production) == [library]

        # Now one party thinks the library is in the testing stage.
        library.registry_stage = Library.TESTING_STAGE

        # It shows up in the testing feed but not the production feed.
        assert feed(db_session, True) == []
        assert feed(db_session, False) == [library]

        library.library_stage = Library.TESTING_STAGE
        library.registry_stage = Library.PRODUCTION_STAGE
        assert feed(db_session, True) == []
        assert feed(db_session, False) == [library]

        # Now on party thinks the library is in the cancelled stage,
        # and it will not show up in eithre feed.
        library.library_stage = Library.CANCELLED_STAGE
        for production in (True, False):
            assert feed(db_session, production) == []

    def test_set_hyperlink(self, db_session, create_test_library):
        library = create_test_library(db_session)

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
        assert link == link2
        assert link2.rel == "rel"
        assert link2.href == "href1"
        assert is_modified is False

        # If there is no way to keep a Hyperlink's href intact,
        # set_hyperlink will modify it.
        link3, is_modified = library.set_hyperlink("rel", "href2", "href3")
        assert link == link3
        assert link3.rel == "rel"
        assert link3.href == "href2"
        assert is_modified is True

        # Under no circumstances will two hyperlinks for the same rel be
        # created for a given library.
        assert library.hyperlinks == [link3]

        # However, a library can have multiple hyperlinks to the same
        # Resource using different rels.
        link4, modified = library.set_hyperlink("rel2", "href2")
        assert link3.resource == link4.resource
        assert modified is True

        # And two libraries can link to the same Resource using the same rel.
        library2 = create_test_library(db_session)
        link5, modified = library2.set_hyperlink("rel2", "href2")
        assert modified is True
        assert link5.library == library2
        assert link5.resource == link4.resource

    def test_get_hyperlink(self, db_session, create_test_library):
        library = create_test_library(db_session)
        link1, is_modified = library.set_hyperlink("contact_email", "contact_href")
        link2, is_modified = library.set_hyperlink("help_email", "help_href")

        contact_link = Library.get_hyperlink(library, "contact_email")
        assert link1 == contact_link

        help_link = Library.get_hyperlink(library, "help_email")
        assert link2 == help_link

    def test_library_service_area(self, db_session, create_test_library, create_test_place):
        a_place = create_test_place(db_session)
        a_library = create_test_library(db_session, eligibility_areas=[a_place])
        [service_area] = a_library.service_areas
        assert service_area.place == a_place
        assert service_area.library == a_library

    @pytest.mark.skip(reason="The relevant() function is extremely complex. Need help debugging this failure.")
    def test_relevant_audience(self, db_session, create_test_library, create_test_place):
        fc_latitude = "37.0"
        fc_longitude = "-109.04"
        four_corners = create_test_place(
            db_session,
            place_type=Place.COUNTY,
            geometry=f"SRID=4326;POINT({fc_latitude} {fc_longitude})"
        )

        lib_common_kwargs = {"eligibility_areas": [four_corners], "focus_areas": [four_corners]}
        research = create_test_library(db_session, audiences=[Audience.RESEARCH], **lib_common_kwargs)
        public = create_test_library(db_session, audiences=[Audience.PUBLIC], **lib_common_kwargs)
        education = create_test_library(
            db_session,
            audiences=[Audience.EDUCATIONAL_PRIMARY, Audience.EDUCATIONAL_SECONDARY],
            **lib_common_kwargs
        )
        db_session.flush()

        [(lib, s)] = Library.relevant(
            db_session,
            (fc_latitude, fc_longitude),
            'eng',
            audiences=[Audience.PUBLIC]
        ).most_common()
        assert lib == public

        [(lib1, s1), (lib2, s2)] = Library.relevant(
            db_session, 
            (fc_latitude, fc_longitude),
            'eng',
            audiences=[Audience.RESEARCH]
        ).most_common()
        assert lib1 == research
        assert lib2 == public

        [(lib1, s1), (lib2, s2)] = Library.relevant(
            db_session, 
            (fc_latitude, fc_longitude),
            'eng',
            audiences=[Audience.EDUCATIONAL_PRIMARY]
        ).most_common()
        assert lib1 == education
        assert lib2 == public

    @pytest.mark.skip(reason="The relevant() function is extremely complex. Need help debugging this failure.")
    def test_relevant_collection_size(self, db_session, create_test_library, places):
        common_kwargs = {"focus_areas": [places["new_york_city"]], "eligibility_areas": [places["new_york_city"]]}

        small = create_test_library(db_session, library_name="Small Library", **common_kwargs)
        CollectionSummary.set(small, "eng", 10)

        large = create_test_library(db_session, library_name="Large Library", **common_kwargs)
        CollectionSummary.set(large, "eng", 100000)

        empty = create_test_library(db_session, library_name="Empty Library", **common_kwargs)
        CollectionSummary.set(empty, "eng", 0)

        unknown = create_test_library(db_session, library_name="Unknown Library", **common_kwargs)
        db_session.flush()

        [(lib1, s1), (lib2, s2), (lib3, s3)] = Library.relevant(db_session, (40.65, -73.94), 'eng').most_common()
        assert lib1 == large
        assert lib2 == small
        assert lib3 == unknown
        # Empty isn't included because we're sure it has no books in English.

    def test_relevant_eligibility_area(self, db_session, create_test_library, places):
        # Create two libraries. One serves New York City, and one serves
        # the entire state of Connecticut. They have the same focus area
        # so this only tests eligibility area.
        nypl = create_test_library(
            db_session,
            library_name="New York Public Library",
            eligibility_areas=[places["new_york_city"]],
            focus_areas=[places["new_york_city"], places["connecticut_state"]]
        )
        ct_state = create_test_library(
            db_session,
            library_name="Connecticut State Library",
            eligibility_areas=[places["connecticut_state"]],
            focus_areas=[places["new_york_city"], places["connecticut_state"]]
        )
        db_session.flush()

        # From this point in Brooklyn, NYPL is the closest library.
        [(lib1, s1), (lib2, s2)] = Library.relevant(db_session, (40.65, -73.94), 'eng').most_common()
        assert lib1 == nypl
        assert lib2 == ct_state

        # From this point in Connecticut, CT State is the closest.
        [(lib1, s1), (lib2, s2)] = Library.relevant(db_session, (41.3, -73.3), 'eng').most_common()
        assert lib1 == ct_state
        assert lib2 == nypl

        # From this point in New Jersey, NYPL is closest.
        [(lib1, s1), (lib2, s2)] = Library.relevant(db_session, (40.72, -74.47), 'eng').most_common()
        assert lib1 == nypl
        assert lib2 == ct_state

        # From this point in the Indian Ocean, both libraries
        # are so far away they're below the score threshold.
        assert list(Library.relevant(db_session, (-15, 91), 'eng').most_common()) == []

    def test_nearby(self, db_session, create_test_library, places):
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

        # From this point in Pennsylvania, NYPL shows up (142km away) but CT State does not.
        [(lib1, d1)] = Library.nearby(self._db, (40, -75.8))
        assert lib1 == nypl
        assert int(d1/1000) == 142

        # If we only look within a 100km radius, then there are no
        # libraries near that point in Pennsylvania.
        assert Library.nearby(self._db, (40, -75.8), 100).all() == []

        # By default, nearby() only finds libraries that are in production.
        def m(production):
            return Library.nearby(self._db, (41.3, -73.3), production=production).count()

        # Take all the libraries we found earlier out of production.
        for lib in ct_state, nypl:
            lib.registry_stage = Library.TESTING_STAGE
        # Now there are no results.
        assert m(True) == 0

        # But we can run a search that includes libraries in the TESTING stage.
        assert m(False) == 2