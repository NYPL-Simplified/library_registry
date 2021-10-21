from sqlalchemy.orm.exc import (MultipleResultsFound, NoResultFound)


class MockPlace:
    """Used to test AuthenticationDocument.parse_coverage."""
    ##### Class Constants ####################################################  # noqa: E266

    AMBIGUOUS = object()    # Indicates a place name is ambiguous
    EVERYWHERE = object()   # Indicates coverage through universe or a country
    _default_nation = None  # Starting point for place names that don't mention a nation
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
