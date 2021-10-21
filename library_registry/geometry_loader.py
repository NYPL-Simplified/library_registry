import json

from library_registry.model import (Place, PlaceAlias)
from library_registry.model_helpers import (get_one_or_create)
from library_registry.util import GeometryUtility


class GeometryLoader:
    """
    Load Place objects from a NDJSON document like that generated by geojson-places-us.
    """
    def __init__(self, _db):
        self._db = _db
        self.places_by_external_id = {}

    def load_ndjson(self, fh):
        while True:
            metadata = fh.readline().strip()

            if not metadata:    # End of file.
                break

            geometry = fh.readline().strip()
            yield self.load(metadata, geometry)

    def load(self, metadata, geometry):
        metadata = json.loads(metadata)
        external_id = metadata['id']
        type = metadata['type']
        parent_external_id = metadata['parent_id']
        name = metadata['name']
        aliases = metadata.get('aliases', [])
        abbreviated_name = metadata.get('abbreviated_name', None)

        if parent_external_id:
            parent = self.places_by_external_id[parent_external_id]
        else:
            parent = None

        # This gives us a Geometry object. Set its SRID so the database
        # knows it's using real-world latitude and longitude.
        geometry = GeometryUtility.from_geojson(geometry)
        (place, is_new) = get_one_or_create(self._db, Place, external_id=external_id, type=type,
                                            parent=parent, create_method_kwargs={"geometry": geometry})

        # Set these values, even the ones that were set in create_method_kwargs, so that we can update
        # any that have changed.
        place.external_name = name
        place.abbreviated_name = abbreviated_name
        place.geometry = geometry

        # We only ever add aliases. If the database contains an alias for this place that doesn't
        # show up in the metadata, it may have been created manually.
        for alias in aliases:
            (alias, _) = get_one_or_create(
                self._db, PlaceAlias, place=place, name=alias['name'], language=alias['language']
            )

        self.places_by_external_id[external_id] = place

        return place, is_new
