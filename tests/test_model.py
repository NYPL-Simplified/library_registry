import datetime

from library_registry.config import Configuration
from library_registry.emailer import Emailer
from library_registry.model import (
    ConfigurationSetting,
    Hyperlink,
)

from . import (
    DatabaseTest,
)


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
