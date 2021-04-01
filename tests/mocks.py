from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound


class MockPlace:
    """Used to test AuthenticationDocument.parse_coverage."""
    AMBIGUOUS = object()    # Used to indicate that a place name is ambiguous.
    EVERYWHERE = object()   # Used to indicate coverage through the universe or through a country.

    # Used within a test to provide a starting point for place names that don't mention a nation.
    _default_nation = None

    by_name = dict()

    def __init__(self, inside=None):
        self.inside = inside or dict()
        self.abbreviated_name = None

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

    def lookup_inside(self, name):
        place = self.inside.get(name)
        if place is self.AMBIGUOUS:
            raise MultipleResultsFound()
        if place is None:
            raise NoResultFound()
        return place

    @classmethod
    def everywhere(cls, _db):
        return cls.EVERYWHERE
