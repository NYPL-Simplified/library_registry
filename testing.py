from datetime import datetime, timedelta
from io import BytesIO
import json
import os

from sqlalchemy.orm.session import Session
from sqlalchemy.orm.exc import (
    NoResultFound,
    MultipleResultsFound,
)

from config import Configuration
from log import LogConfiguration
from model import (
    get_one_or_create,
    Admin,
    Audience,
    Base,
    ConfigurationSetting,
    ExternalIntegration,
    Hyperlink,
    Library,
    Place,
    PlaceAlias,
    ServiceArea,
    SessionManager,
)
from util import GeometryUtility
from util.http import BadResponseException


def package_setup():
    """Make sure the database schema is initialized and initial
    data is in place.
    """
    engine, connection = DatabaseTest.get_database_connection()

    # First, recreate the schema.
    for table in reversed(Base.metadata.sorted_tables):
        engine.execute(table.delete())

    Base.metadata.create_all(connection)

    # Initialize basic database data needed by the application.
    _db = Session(connection)
    SessionManager.initialize_data(_db)
    _db.commit()

    LogConfiguration.initialize(_db)

    connection.close()
    engine.dispose()


class DummyHTTPResponse():
    def __init__(self, status_code, headers, content, links=None, url=None):
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.links = links or {}
        self.url = url or "http://url/"

    @property
    def raw(self):
        return BytesIO(self.content)


class DummyHTTPClient():

    def __init__(self):
        self.responses = []
        self.requests = []

    def queue_response(self, response_code, media_type="text/html",
                       other_headers=None, content='', links=None,
                       url=None):
        headers = {}
        if media_type:
            headers["Content-Type"] = media_type
        if other_headers:
            for k, v in list(other_headers.items()):
                headers[k.lower()] = v
        self.responses.insert(
            0, DummyHTTPResponse(response_code, headers, content, links, url)
        )

    def do_get(self, url, headers=None, allowed_response_codes=None, **kwargs):
        self.requests.append(url)
        response = self.responses.pop()
        if isinstance(response.status_code, Exception):
            raise response.status_code

        # Simulate the behavior of requests, where response.url contains
        # the final URL that responded to the request.
        response.url = url

        code = response.status_code
        series = "%sxx" % (code // 100)

        if allowed_response_codes and (code not in allowed_response_codes and series not in allowed_response_codes):
            raise BadResponseException(url, "Bad Response!", status_code=code)
        return response


class MockRequestsResponse():
    """A mock object that simulates an HTTP response from the
    `requests` library.
    """
    def __init__(self, status_code, headers={}, content=None, url=None):
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.url = url or "http://url/"

    def json(self):
        content = self.content
        # The queued content might be a JSON string or it might
        # just be the object you'd get from loading a JSON string.
        if isinstance(content, (bytes, str)):
            content = json.loads(self.content)
        return content

    @property
    def text(self):
        return self.content.decode("utf8")


class MockPlace():
    """Used to test AuthenticationDocument.parse_coverage."""

    # Used to indicate that a place name is ambiguous.
    AMBIGUOUS = object()

    # Used to indicate coverage through the universe or through a
    # country.
    EVERYWHERE = object()

    # Used within a test to provide a starting point for place
    # names that don't mention a nation.
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
