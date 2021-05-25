##############################################################################
# Sitewide Configuration Value Names
##############################################################################

ADOBE_VENDOR_ID = "vendor_id"

ADOBE_VENDOR_ID_NODE_VALUE = "node_value"

ADOBE_VENDOR_ID_DELEGATE_URL = "delegate_url"

BASE_URL = "base_url"

# Default nation for any place not explicitly in a particular nation.
DEFAULT_NATION_ABBREVIATION = "default_nation_abbreviation"

# For performance reasons, a registry may want to omit certain pieces of information from
# large feeds. This sitewide setting controls how big a feed must be to be considered 'large'.
LARGE_FEED_SIZE = "large_feed_size"

# URL of the terms of service document for library registration
REGISTRATION_TERMS_OF_SERVICE_URL = "registration_terms_of_service_url"

# HTML snippet describing the ToS for library registration. It's better if this
# is a short snippet of text with a link rather than the actual text of the ToS.
REGISTRATION_TERMS_OF_SERVICE_HTML = "registration_terms_of_service_html"

# Email address used for:
#   - From: address of transactional mail sent by the Library Registry
#   - contact address for people having problems with the registry
REGISTRY_CONTACT_EMAIL = "registry_contact_email"

# URL of a web based client to the registry. Must be templated and contain
# a `{uuid}` expression to provide the web URL for a specific library.
WEB_CLIENT_URL = "web_client_url"

##############################################################################
# Media Types
##############################################################################

AUTHENTICATION_DOCUMENT_MEDIA_TYPE = "application/vnd.opds.authentication.v1.0+json"

PROBLEM_DETAIL_JSON_MEDIA_TYPE = "application/api-problem+json"

OPDS_MEDIA_TYPE = "application/opds+json"

OPDS_CATALOG_MEDIA_TYPE = "application/atom+xml;profile=opds-catalog"

OPDS_1_MEDIA_TYPE = f"{OPDS_CATALOG_MEDIA_TYPE};kind=acquisition"

OPDS_CATALOG_REGISTRATION_MEDIA_TYPE = (
    "application/opds+json;profile=https://librarysimplified.org/rel/profile/directory"
)

OPENSEARCH_MEDIA_TYPE = "application/opensearchdescription+xml"

##############################################################################
# Relation URIs
##############################################################################

##############################################################################
# Place Types
##############################################################################
PLACE_NATION                  = 'nation'                  # noqa: E221
PLACE_STATE                   = 'state'                   # noqa: E221
PLACE_COUNTY                  = 'county'                  # noqa: E221
PLACE_CITY                    = 'city'                    # noqa: E221
PLACE_POSTAL_CODE             = 'postal_code'             # noqa: E221
PLACE_LIBRARY_SERVICE_AREA    = 'library_service_area'    # noqa: E221
PLACE_EVERYWHERE              = 'everywhere'              # noqa: E221
