import json
import random
import re
import uuid

import pytest

from constants import LibraryType
from model import (
    DelegatedPatronIdentifier,
    Hyperlink,
    Library,
    Place,
)
from util.geo import Location


GENERATED_SHORT_NAME_REGEX = re.compile(r'^[A-Z]{6}$')

##############################################################################
# Note: The test_nearby_* functions rely on Libraries and Places created
#       by the following fixtures. The locations are in central Kansas, USA (for
#       no other reason than it's square and grid-like out there, so was
#       easy to eyeball locations in Google Maps). They are laid out like the
#       following diagram. Each of the points, P1-P6, are labeled with their
#       respective distance ordering of libraries A, B, and C.
#
#                        P1(ABC)
#
#
#
#
#
#  P6(BAC)                   Lib A                  P2(ACB)
#                          (Beloit, KS)
#
#
#
#                 Lib B
#               (Russell, KS)
#
#
#
#
#  P5(BCA)                   Lib C                  P3(CAB)
#                        (Hutchinson, KS)
#
#
#
#
#                         P4(CBA)
#
##############################################################################


def latlong_square_polygon(latitude, longitude, offset=0.02):
    """
    For a given lat/long centerpoint, returns five coordinate
    pairs that describe a square whose edges are 0.02 (or `offset`) degrees
    out from that point.

    The return list is five elements because a GeoJSON polygon
    is described by a closed ring, so the first and last coordinates
    must be the same. The multiple nesting levels are also a GeoJSON requirement.

    Note: This isn't a general purpose function, it probably only
    works for points in North America that are positive latitude,
    negative longitude. I just needed some boxes in Kansas.
    """
    return [[
        [round(longitude - offset, 6), round(latitude + offset, 6)],
        [round(longitude + offset, 6), round(latitude + offset, 6)],
        [round(longitude + offset, 6), round(latitude - offset, 6)],
        [round(longitude - offset, 6), round(latitude - offset, 6)],
        [round(longitude - offset, 6), round(latitude + offset, 6)],    # same as the first point
    ]]


@pytest.fixture
def nearby_lib_a(db_session, create_test_place, create_test_library):
    """Library whose service area is a rectangle around Beloit, KS"""
    (latitude, longitude) = (39.465359, -98.109062)
    libname = "ALPHA"
    svc_area_geometry = {"type": "Polygon", "coordinates": latlong_square_polygon(latitude, longitude)}
    svc_area = create_test_place(db_session, external_id=f"lib_{libname}_svc_area", place_type=Place.CITY,
                                 geometry=json.dumps(svc_area_geometry))
    lib = create_test_library(db_session, library_name=libname, focus_areas=[svc_area],
                              eligibility_areas=[svc_area])
    db_session.commit()
    yield lib
    db_session.delete(lib)
    db_session.delete(svc_area)
    db_session.commit()


@pytest.fixture
def nearby_lib_b(db_session, create_test_place, create_test_library):
    """Library whose service area is a rectangle around Russell, KS"""
    (latitude, longitude) = (38.892131, -98.856232)
    libname = "BRAVO"
    svc_area_geometry = {"type": "Polygon", "coordinates": latlong_square_polygon(latitude, longitude)}
    svc_area = create_test_place(db_session, external_id=f"lib_{libname}_svc_area", place_type=Place.CITY,
                                 geometry=json.dumps(svc_area_geometry))
    lib = create_test_library(db_session, library_name=libname, focus_areas=[svc_area],
                              eligibility_areas=[svc_area])
    db_session.commit()
    yield lib
    db_session.delete(lib)
    db_session.delete(svc_area)
    db_session.commit()


@pytest.fixture
def nearby_lib_c(db_session, create_test_place, create_test_library):
    """Library whose service area is a rectangle around Hutchinson, KS"""
    (latitude, longitude) = (38.068448, -97.921910)
    libname = "CHARLIE"
    svc_area_geometry = {"type": "Polygon", "coordinates": latlong_square_polygon(latitude, longitude)}
    svc_area = create_test_place(db_session, external_id=f"lib_{libname}_svc_area", place_type=Place.CITY,
                                 geometry=json.dumps(svc_area_geometry))
    lib = create_test_library(db_session, library_name=libname, focus_areas=[svc_area],
                              eligibility_areas=[svc_area])
    db_session.commit()
    yield lib
    db_session.delete(lib)
    db_session.delete(svc_area)
    db_session.commit()


@pytest.fixture
def nearby_libs(nearby_lib_a, nearby_lib_b, nearby_lib_c):
    """All three nearby_lib_* fixtures in a dict"""
    return {
        "nearby_lib_a": nearby_lib_a,
        "nearby_lib_b": nearby_lib_b,
        "nearby_lib_c": nearby_lib_c,
    }


@pytest.fixture
def state_lib_d(db_session, create_test_place, create_test_library):
    """Library whose service area is the western half of Kansas"""
    libname = "DELTA"
    svc_area_geometry = {
                            "type": "Polygon",
                            "coordinates": [[
                                [-102.049880, 39.999859],
                                [-98.535992, 39.998648],
                                [-98.535992, 36.990382],
                                [-102.041553, 36.990382],
                                [-102.049880, 39.999859],
                            ]]
                        }
    svc_area = create_test_place(db_session, external_id=f"lib_{libname}_svc_area",
                                 place_type=Place.STATE, geometry=json.dumps(svc_area_geometry))
    lib = create_test_library(db_session, library_name=libname, focus_areas=[svc_area],
                              eligibility_areas=[svc_area])
    db_session.commit()
    yield lib
    db_session.delete(lib)
    db_session.delete(svc_area)
    db_session.commit()


@pytest.fixture
def state_lib_e(db_session, create_test_place, create_test_library):
    """Library whose service area is the eastern half of Kansas"""
    libname = "ECHO"
    svc_area_geometry = {
                            "type": "Polygon",
                            "coordinates": [[
                                [-98.535992, 39.998648],
                                [-94.876420, 39.998648],
                                [-94.876420, 36.990382],
                                [-98.535992, 36.990382],
                                [-98.535992, 39.998648],
                            ]]
                        }
    svc_area = create_test_place(db_session, external_id=f"lib_{libname}_svc_area",
                                 place_type=Place.STATE, geometry=json.dumps(svc_area_geometry))
    lib = create_test_library(db_session, library_name=libname, focus_areas=[svc_area],
                              eligibility_areas=[svc_area])
    db_session.commit()
    yield lib
    db_session.delete(lib)
    db_session.delete(svc_area)
    db_session.commit()


@pytest.fixture
def state_lib_f(db_session, create_test_place, create_test_library):
    """Library whose service area is the state of Colorado"""
    libname = "FOXTROT"
    svc_area_geometry = {
                            "type": "Polygon",
                            "coordinates": [[
                                [-109.060023, 41.001758],
                                [-102.040416, 41.001758],
                                [-102.040416, 37.004643],
                                [-109.060023, 37.004643],
                                [-109.060023, 41.001758],
                            ]]
                        }
    svc_area = create_test_place(db_session, external_id=f"lib_{libname}_svc_area",
                                 place_type=Place.STATE, geometry=json.dumps(svc_area_geometry))
    lib = create_test_library(db_session, library_name=libname, focus_areas=[svc_area],
                              eligibility_areas=[svc_area])
    db_session.commit()
    yield lib
    db_session.delete(lib)
    db_session.delete(svc_area)
    db_session.commit()


@pytest.fixture
def state_libs(state_lib_d, state_lib_e, state_lib_f):
    """All state level libraries in a dict"""
    return {
        "state_lib_d": state_lib_d,
        "state_lib_e": state_lib_e,
        "state_lib_f": state_lib_f,
    }


class TestLibraryModel:
    def test_short_name_validation(self, nypl):
        """
        GIVEN: An existing Library object
        WHEN:  The .short_name field of that object is set to a string containing a pipe
        THEN:  A ValueError is raised
        """
        with pytest.raises(ValueError) as exc:
            nypl.short_name = "ab|cd"
        assert "Short name cannot contain the pipe character" in str(exc.value)

    def test_for_short_name(self, db_session, nypl):
        """
        GIVEN: An existing Library with a given short_name value
        WHEN:  The Library.for_short_name() class method is called with that short_name value
        THEN:  The appropriate Library object should be returned
        """
        assert Library.for_short_name(db_session, 'NYPL') == nypl

    def test_for_urn(self, db_session, nypl):
        """
        GIVEN: An existing library with a given internal_urn value
        WHEN:  The Library.for_urn() class method is called with that internal_urn value
        THEN:  The appropriate Library object should be returned
        """
        assert Library.for_urn(db_session, nypl.internal_urn) == nypl

    def test_random_short_name(self):
        """
        GIVEN: A pre-determined seed for the Python random library
        WHEN:  The Library.random_short_name() class method is called
        THEN:  A seed-determined value or values are generated which are six ascii uppercase characters
        """
        random.seed(42)
        SEED_42_FIRST_VALUE = "UDAXIH"
        generated_name = Library.random_short_name()
        assert generated_name == SEED_42_FIRST_VALUE
        assert re.match

    def test_random_short_name_duplicate_check(self):
        """
        GIVEN: A duplicate check function indicating a seeded name is already in use
        WHEN:  The Library.random_short_name() function is called with that function
        THEN:  The next seeded name value should be returned
        """
        random.seed(42)
        SEED_42_FIRST_VALUE = "UDAXIH"
        SEED_42_SECOND_VALUE = "HEXDVX"

        assert Library.random_short_name() == SEED_42_FIRST_VALUE     # Call once to move past initial value
        name = Library.random_short_name(duplicate_check=lambda x: x == SEED_42_FIRST_VALUE)
        assert name == SEED_42_SECOND_VALUE

    def test_random_short_name_quit_after_20_attempts(self):
        """
        GIVEN: A duplicate check function which always indicates a duplicate name exists
        WHEN:  Library.random_short_name() is called with that duplicate check
        THEN:  A ValueError should be raised indicating no short name could be generated
        """
        with pytest.raises(ValueError) as exc:
            Library.random_short_name(duplicate_check=lambda x: True)
        assert "Could not generate random short name after 20 attempts!" in str(exc.value)

    def test_set_library_stage(self, db_session, nypl):
        """
        GIVEN: An existing Library that the registry has put in production
        WHEN:  An attempt is made to set the .library_stage for that Library
        THEN:  A ValueError should be raised, because the .registry_stage gates .library_stage
        """
        # The .library_stage may not be changed while .registry_stage is PRODUCTION_STAGE
        with pytest.raises(ValueError) as exc:
            nypl.library_stage = Library.TESTING_STAGE
        assert "This library is already in production" in str(exc.value)

        # Have the registry take the library out of production.
        nypl.registry_stage = Library.CANCELLED_STAGE
        assert nypl.in_production is False

        # Now we can change the library stage however we want.
        nypl.library_stage = Library.TESTING_STAGE
        nypl.library_stage = Library.CANCELLED_STAGE
        nypl.library_stage = Library.PRODUCTION_STAGE

    def test_in_production(self, nypl):
        """
        GIVEN: An existing Library in PRODUCTION_STAGE
        WHEN:  Either .registry_stage or .library_stage is set to CANCELLED_STAGE
        THEN:  The Library's .in_production property should return False
        """
        assert nypl.library_stage == Library.PRODUCTION_STAGE
        assert nypl.registry_stage == Library.PRODUCTION_STAGE
        assert nypl.in_production is True

        # If either library_stage or registry stage is not
        # PRODUCTION_STAGE, we are not in production.
        nypl.registry_stage = Library.CANCELLED_STAGE
        assert nypl.in_production is False

        nypl.library_stage = Library.CANCELLED_STAGE
        assert nypl.in_production is False

        nypl.registry_stage = Library.PRODUCTION_STAGE
        assert nypl.in_production is False

    def test_number_of_patrons(self, db_session, create_test_library):
        """
        GIVEN: A newly created Library in Producion stage
        WHEN:  A DelegatedPatronIdentifier with an Adobe Account ID is associated with that Library
        THEN:  The Library's .number_of_patrons property should reflect that patron
        """
        lib = create_test_library(db_session)
        assert lib.number_of_patrons == 0
        (identifier, _) = DelegatedPatronIdentifier.get_one_or_create(
            db_session, lib, str(uuid.uuid4()), DelegatedPatronIdentifier.ADOBE_ACCOUNT_ID, None
        )
        assert lib.number_of_patrons == 1

        db_session.delete(lib)
        db_session.delete(identifier)
        db_session.commit()

    def test_number_of_patrons_non_adobe(self, db_session, create_test_library):
        """
        GIVEN: A newly created Library in Production stage
        WHEN:  A DelegatedPatronIdentifier without an Adobe Account ID is associated with that Library
        THEN:  The Library's .number_of_patrons property should not increase
        """
        lib = create_test_library(db_session)
        (identifier, _) = DelegatedPatronIdentifier.get_one_or_create(
            db_session, lib, str(uuid.uuid4()), "abc", None
        )
        assert lib.number_of_patrons == 0

        db_session.delete(lib)
        db_session.delete(identifier)
        db_session.commit()

    def test_number_of_patrons_non_production_stage(self, db_session, create_test_library):
        """
        GIVEN: A newly created Library in Testing stage
        WHEN:  A DelegatedPatronIdentifier is created referencing that Library
        THEN:  The Library's .number_of_patrons property should not increase, since identifiers
               cannot be assigned to libraries not in production.
        """
        lib = create_test_library(db_session, library_stage=Library.TESTING_STAGE)
        (identifier, _) = DelegatedPatronIdentifier.get_one_or_create(
            db_session, lib, str(uuid.uuid4()), DelegatedPatronIdentifier.ADOBE_ACCOUNT_ID, None
        )
        assert lib.number_of_patrons == 0

        db_session.delete(lib)
        db_session.delete(identifier)
        db_session.commit()

    def test__feed_restriction_production_stage(self, db_session, create_test_library):
        """
        GIVEN: A Library object whose .registry_stage and .library_stage are both PRODUCTION_STAGE
        WHEN:  The Library._feed_restriction() method is used to filter a Library query
        THEN:  That Production library should be in the result set no matter what boolean value is
               passed to _feed_restriction()
        """
        library = create_test_library(db_session)
        assert library.library_stage == Library.PRODUCTION_STAGE
        assert library.registry_stage == Library.PRODUCTION_STAGE

        # A library in PRODUCTION_STAGE should not be removed by feed restriction
        q = db_session.query(Library)
        assert q.filter(Library._feed_restriction(production=True)).all() == [library]
        assert q.filter(Library._feed_restriction(production=False)).all() == [library]

        db_session.delete(library)
        db_session.commit()

    def test__feed_restriction_mixed_stages(self, db_session, create_test_library):
        """
        GIVEN: A Library object with:
                - .registry_stage set to TESTING_STAGE
                - .library_stage set to PRODUCTION_STAGE
        WHEN:  The Library._feed_restriction() method is used to filter a Library query
        THEN:  The Library should only be returned when the 'production' parameter for
               _feed_restriction() is set to False
        """
        library = create_test_library(db_session)
        library.registry_stage = Library.TESTING_STAGE

        q = db_session.query(Library)
        assert library.registry_stage != library.library_stage
        assert q.filter(Library._feed_restriction(production=True)).all() == []
        assert q.filter(Library._feed_restriction(production=False)).all() == [library]

        db_session.delete(library)
        db_session.commit()

    def test__feed_restriction_testing_stage(self, db_session, create_test_library):
        """
        GIVEN: A Library object in TESTING_STAGE for both .library_stage and .registry_stage
        WHEN:  The Library._feed_restriction() method is used to filter a Library query
        THEN:  The Library should be returned in a testing feed, but not a production feed
        """
        library = create_test_library(db_session)
        library.registry_stage = Library.TESTING_STAGE
        library.library_stage = Library.TESTING_STAGE

        q = db_session.query(Library)
        assert q.filter(Library._feed_restriction(production=True)).all() == []
        assert q.filter(Library._feed_restriction(production=False)).all() == [library]

        db_session.delete(library)
        db_session.commit()

    def test__feed_restriction_cancelled_stage(self, db_session, create_test_library):
        """
        GIVEN: A Library object in CANCELLED_STAGE (for either or both of registry_stage/library_stage)
        WHEN:  The Library._feed_restriction() method is used to filter a Library query
        THEN:  The Library should not be returned in either testing or production feeds
        """
        library = create_test_library(db_session)
        library.registry_stage = Library.CANCELLED_STAGE
        library.library_stage = Library.CANCELLED_STAGE
        q = db_session.query(Library)
        assert q.filter(Library._feed_restriction(production=True)).all() == []
        assert q.filter(Library._feed_restriction(production=False)).all() == []

        db_session.delete(library)
        db_session.commit()

    def test_set_hyperlink_exceptions(self, db_session, create_test_library):
        """
        GIVEN: An existing Library
        WHEN:  The .set_hyperlink() method is called without all necessary parameters
        THEN:  Appropriate exceptions should be raised
        """
        library = create_test_library(db_session)

        with pytest.raises(ValueError) as exc:
            library.set_hyperlink("rel")
        assert "No Hyperlink hrefs were specified" in str(exc.value)

        with pytest.raises(ValueError) as exc:
            library.set_hyperlink(None, ["href"])
        assert "No link relation was specified" in str(exc.value)

        db_session.delete(library)
        db_session.commit()

    def test_set_hyperlink(self, db_session, create_test_library):
        """
        GIVEN: An existing Library object
        WHEN:  .set_hyperlink is called with sufficient arguments
        THEN:  A Hyperlink object should be returned, with is_modified True
        """
        library = create_test_library(db_session)
        (link, is_modified) = library.set_hyperlink("rel", "href1", "href2")
        assert isinstance(link, Hyperlink)
        assert is_modified is True
        assert link.rel == "rel"
        assert link.href == "href1"
        assert link.library_id == library.id

        db_session.delete(library)
        db_session.delete(link)
        db_session.commit()

    def test_set_hyperlink_multiple_calls(self, db_session, create_test_library):
        """
        GIVEN: An existing Library object
        WHEN:  .set_hyperlink is called multiple times, with href parameters in different orders
        THEN:  The href set as default in the original link creation will remain the return value of .href
        """
        library = create_test_library(db_session)
        (link_original, _) = library.set_hyperlink("rel", "href1", "href2")
        # Calling set_hyperlink again does not modify the link so long as the old href is still a possibility.
        (link_new, is_modified) = library.set_hyperlink("rel", "href2", "href1")
        assert link_original == link_new
        assert link_new.rel == "rel"
        assert link_new.href == "href1"
        assert is_modified is False

        db_session.delete(library)
        db_session.delete(link_original)
        db_session.commit()

    def test_set_hyperlink_overwrite_href(self, db_session, create_test_library):
        """
        GIVEN: An existing Library object with a hyperlink with a specific href value
        WHEN:  A subsequent call to .set_hyperlink() provides hrefs which do not include the existing href value
        THEN:  The .href of that Hyperlink will be set to the first of the new values
        """
        library = create_test_library(db_session)
        (link_original, _) = library.set_hyperlink("rel", "href1", "href2")
        (link_modified, is_modified) = library.set_hyperlink("rel", "href2", "href3")
        assert is_modified is True
        assert link_original == link_modified
        assert link_modified.rel == "rel"
        assert link_modified.href == "href2"

        db_session.delete(library)
        db_session.delete(link_original)
        db_session.commit()

    def test_set_hyperlink_one_link_rel_per_library(self, db_session, create_test_library):
        """
        GIVEN: An existing Library object with a hyperlink for a specific rel name
        WHEN:  A second call to .set_hyperlink() is made with the same rel name
        THEN:  The existing hyperlink is either returned or modified--there is never more
               than one hyperlink for a given rel at the same Library
        """
        library = create_test_library(db_session)
        (link_original, _) = library.set_hyperlink("rel", "href1", "href2")
        (link_modified, is_modified) = library.set_hyperlink("rel", "href2", "href3")

        assert library.hyperlinks == [link_modified]

        db_session.delete(library)
        db_session.delete(link_original)
        db_session.commit()

    def test_set_hyperlink_multiple_hyperlinks_same_resource(self, db_session, create_test_library):
        """
        GIVEN: An existing Library object with a hyperlink for a specific rel name
        WHEN:  A second call to .set_hyperlink() is made, for the same resource but a different rel name
        THEN:  A second hyperlink should be created
        """
        library = create_test_library(db_session)
        (link_original, _) = library.set_hyperlink("rel_alpha", "href1")
        (link_new, modified) = library.set_hyperlink("rel_bravo", "href1")
        assert link_original.resource == link_new.resource
        assert modified is True

        db_session.delete(library)
        db_session.delete(link_original)
        db_session.delete(link_new)
        db_session.commit()

    def test_set_hyperlink_two_libraries_link_same_resource_same_rel(self, db_session, create_test_library):
        """
        GIVEN: Two different Library objects:
                - One with an existing hyperlink to a specific rel/resource
                - One without a hyperlink to that rel/resource
        WHEN:  .set_hyperlink() is called for the second library with the same rel/resource
        THEN:  A Hyperlink is successfully created for the second library, with an identical
               rel/resource as for the first library
        """
        link_args = ["some-rel-name", "href-to-resource-001"]
        library_alpha = create_test_library(db_session)
        library_bravo = create_test_library(db_session)
        (link_alpha, is_alpha_modified) = library_alpha.set_hyperlink(*link_args)
        assert isinstance(link_alpha, Hyperlink)
        assert is_alpha_modified is True
        assert link_alpha.library_id == library_alpha.id

        (link_bravo, is_bravo_modified) = library_bravo.set_hyperlink(*link_args)
        assert isinstance(link_bravo, Hyperlink)
        assert is_bravo_modified is True
        assert link_bravo.library_id == library_bravo.id

        assert link_alpha.href == link_bravo.href
        assert link_alpha.rel == link_bravo.rel

        for item in [library_alpha, library_bravo, link_alpha, link_bravo]:
            db_session.delete(item)
        db_session.commit()

    def test_get_hyperlink(self, db_session, create_test_library):
        """
        GIVEN: An existing Library object
        WHEN:  A hyperlink is created associated with that Library for a given rel name
        THEN:  A subsequent call to Library.get_hyperlink() referencing that Library and
               rel name should return an appropriate Hyperlink object
        """
        library = create_test_library(db_session)
        (link1, _) = library.set_hyperlink("contact_email", "contact_href")
        (link2, _) = library.set_hyperlink("help_email", "help_href")

        contact_link = Library.get_hyperlink(library, "contact_email")
        assert isinstance(contact_link, Hyperlink)
        assert link1 == contact_link

        help_link = Library.get_hyperlink(library, "help_email")
        assert isinstance(help_link, Hyperlink)
        assert link2 == help_link

        for item in [library, link1, link2]:
            db_session.delete(item)
        db_session.commit()

    @pytest.mark.skip(reason="Need to implement")
    def test_patron_counts_by_library(self):
        """
        GIVEN: Multiple existing Libraries, each with some number of patrons
        WHEN:  Library.patron_counts_by_library() is passed a list of instances representing those Libraries
        THEN:  A dictionary should be returned with library_id: count entries
        """

    def test_library_service_area(self, db_session, create_test_library, create_test_place):
        """
        GIVEN: An existing Place object
        WHEN:  A Library is created with that Place as the contents of the list passed to the
               Library constructor's eligibility_areas parameter
        THEN:  That Place should be the sole entry in the list returned by .service_areas
        """
        a_place = create_test_place(db_session)
        a_library = create_test_library(db_session, eligibility_areas=[a_place])
        [service_area] = a_library.service_areas
        assert service_area.place == a_place
        assert service_area.library == a_library

        db_session.delete(a_library)
        db_session.delete(a_place)
        db_session.commit()

    @pytest.mark.skip(reason="Merged in from develop, needs edits")
    def test_types(self, db_session, create_test_place, create_test_library, zip_10018, new_york_city, new_york_state):
        """
        GIVEN:
        WHEN:
        THEN:
        """
        postal = zip_10018
        city = new_york_city
        state = new_york_state
        nation = create_test_place(db_session, external_id='CA', external_name='Canada',
                                   place_type=Place.NATION, abbreviated_name='CA')
        province = create_test_place(db_session, external_id="MB", external_name="Manitoba",
                                     place_type=Place.STATE, abbreviated_name="MB", parent=nation)
        everywhere = Place.everywhere(db_session)

        # Libraries with different kinds of service areas are given different types.
        for focus, type in (
            (postal, LibraryType.LOCAL),
            (city, LibraryType.LOCAL),
            (state, LibraryType.STATE),
            (province, LibraryType.PROVINCE),
            (nation, LibraryType.NATIONAL),
            (everywhere, LibraryType.UNIVERSAL)
        ):
            library = create_test_library(db_session, focus_areas=[focus])
            assert focus.library_type == type
            assert [type] == list(library.types)
            db_session.delete(library)
            db_session.commit()

        # If a library's service area is ambiguous, it has no service area-related type.
        library = create_test_library(db_session, library_name="library", focus_areas=[postal, province])
        assert [] == list(library.types)
        db_session.delete(library)
        db_session.delete(nation)
        db_session.delete(province)
        db_session.commit()

    @pytest.mark.parametrize(
        "location,liborder",
        [
            pytest.param((39.733073, -97.856284), ["ALPHA", "BRAVO", "CHARLIE"], id="P1"),
            pytest.param((39.014456, -97.028744), ["ALPHA", "CHARLIE", "BRAVO"], id="P2"),
            pytest.param((38.581711, -96.801934), ["CHARLIE", "ALPHA", "BRAVO"], id="P3"),
            pytest.param((37.798725, -98.024885), ["CHARLIE", "BRAVO", "ALPHA"], id="P4"),
            pytest.param((38.577897, -99.070922), ["BRAVO", "CHARLIE", "ALPHA"], id="P5"),
            pytest.param((39.085152, -99.012190), ["BRAVO", "ALPHA", "CHARLIE"], id="P6"),
        ]
    )
    def test_nearby_all(self, db_session, nearby_libs, capsys, location, liborder):
        """
        GIVEN: A known set of three Libraries and a known set of six locations
        WHEN:  Library.nearby() is called for a location, with 1000km radius
        THEN:  The returned set of three Libraries should be in the correct distance order
        """
        found_libs = Library.nearby(db_session, Location(location), max_radius=1000).all()
        assert len(found_libs) == 3
        assert [x[0].name for x in found_libs] == liborder

    @pytest.mark.parametrize(
        "location,liborder",
        [
            pytest.param((39.733073, -97.856284), ["ALPHA", "BRAVO"], id="P1_150km"),
            pytest.param((39.014456, -97.028744), ["ALPHA", "CHARLIE"], id="P2_150km"),
            pytest.param((38.581711, -96.801934), ["CHARLIE", "ALPHA"], id="P3_150km"),
            pytest.param((37.798725, -98.024885), ["CHARLIE", "BRAVO"], id="P4_150km"),
            pytest.param((38.577897, -99.070922), ["BRAVO", "CHARLIE", "ALPHA"], id="P5_150km"),
            pytest.param((39.085152, -99.012190), ["BRAVO", "ALPHA", "CHARLIE"], id="P6_150km"),
        ]
    )
    def test_nearby_150km(self, db_session, nearby_libs, capsys, location, liborder):
        """
        GIVEN: A known set of three Libraries and a known set of six locations
        WHEN:  Library.nearby() is called for a location, with 150km radius
        THEN:  The returned set of Libraries should be limited to those in range
        """
        found_libs = Library.nearby(db_session, Location(location), max_radius=150).all()
        assert [x[0].name for x in found_libs] == liborder

    @pytest.mark.parametrize(
        "location,liborder",
        [
            pytest.param((39.733073, -97.856284), ["ECHO", "DELTA", "FOXTROT"], id="P1"),
            pytest.param((39.014456, -97.028744), ["ECHO", "DELTA", "FOXTROT"], id="P2"),
            pytest.param((38.581711, -96.801934), ["ECHO", "DELTA", "FOXTROT"], id="P3"),
            pytest.param((37.798725, -98.024885), ["ECHO", "DELTA", "FOXTROT"], id="P4"),
            pytest.param((38.577897, -99.070922), ["DELTA", "ECHO", "FOXTROT"], id="P5"),
            pytest.param((39.085152, -99.012190), ["DELTA", "ECHO", "FOXTROT"], id="P6"),
            pytest.param((38.645276, -101.857932), ["DELTA", "FOXTROT", "ECHO"], id="P7_western_KS"),
        ]
    )
    def test_nearest_supralocal(self, db_session, nearby_libs, state_libs, location, liborder):
        """
        GIVEN: A known set of
        WHEN:
        THEN:
        """
        found_supra_libs = Library.nearest_supralocals(db_session, Location(location), max_radius=1000).all()
        assert [x[0].name for x in found_supra_libs] == liborder
