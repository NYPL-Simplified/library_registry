from io import BytesIO

from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound


class MockPlace:
    """Used to test AuthenticationDocument.parse_coverage."""
    ##### Class Constants ####################################################  # noqa: E266
    AMBIGUOUS = object()    # Used to indicate that a place name is ambiguous.
    EVERYWHERE = object()   # Used to indicate coverage through the universe or through a country.

    # Used within a test to provide a starting point for place names that don't mention a nation.
    _default_nation = None

    by_name = dict()

    ##### Public Interface / Magic Methods ###################################  # noqa: E266
    def __init__(self, inside=None):
        self.inside = inside or dict()
        self.abbreviated_name = None

    def lookup_inside(self, name):
        place = self.inside.get(name)
        if place is self.AMBIGUOUS:
            raise MultipleResultsFound()
        if place is None:
            raise NoResultFound()
        return place

    ##### Private Methods ####################################################  # noqa: E266

    ##### Properties and Getters/Setters #####################################  # noqa: E266

    ##### Class Methods ######################################################  # noqa: E266
    @classmethod
    def default_nation(cls, _db):
        return cls._default_nation

    @classmethod
    def lookup_one_by_name(cls, _db, name, place_type):
        place = cls.by_name.get(name)
        if place is cls.AMBIGUOUS:
            raise MultipleResultsFound()
        if place is None:
            raise NoResultFound()
        print("%s->%s" % (name, place))
        return place

    @classmethod
    def everywhere(cls, _db):
        return cls.EVERYWHERE

    ##### Private Class Methods ##############################################  # noqa: E266


class DummyHTTPResponse:
    def __init__(self, status_code, headers, content, links=None, url=None):
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.links = links or {}
        self.url = url or "http://url/"

    @property
    def raw(self):
        return BytesIO(self.content)
