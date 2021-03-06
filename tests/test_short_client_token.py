import base64
from nose.tools import (
    eq_,
    set_trace,
    assert_raises_regexp
)
import logging
from util.short_client_token import ShortClientTokenEncoder
from model import (
    DelegatedPatronIdentifier,
    ShortClientTokenDecoder,
)

from . import DatabaseTest

class TestShortClientTokenEncoder(object):

    def setup(self):
        self.encoder = ShortClientTokenEncoder()

    def test_adobe_base64_encode_decode(self):
        # Test our special variant of base64 encoding designed to avoid
        # triggering an Adobe bug.
        value = b"!\tFN6~'Es52?X!#)Z*_S"

        encoded = self.encoder.adobe_base64_encode(value)
        eq_(b'IQlGTjZ:J0VzNTI;WCEjKVoqX1M@', encoded)

        # This is like normal base64 encoding, but with a colon
        # replacing the plus character, a semicolon replacing the
        # slash, an at sign replacing the equal sign and the final
        # newline stripped.
        eq_(
            encoded.replace(b":", b"+").replace(b";", b"/").replace(b"@", b"=") + b"\n",
            base64.encodestring(value)
        )

        # We can reverse the encoding to get the original value.
        eq_(value, self.encoder.adobe_base64_decode(encoded))

    def test_encode_short_client_token_uses_adobe_base64_encoding(self):
        class MockSigner(object):
            def prepare_key(self, key):
                return key
            def sign(self, value, key):
                """Always return the same signature, crafted to contain a
                plus sign, a slash and an equal sign when base64-encoded.
                """
                return "!\tFN6~'Es52?X!#)Z*_S"
        self.encoder.signer = MockSigner()
        token = self.encoder._encode("lib", "My library secret", "1234", 0)

        # The signature part of the token has been encoded with our
        # custom encoding, not vanilla base64.
        eq_('lib|0|1234|IQlGTjZ:J0VzNTI;WCEjKVoqX1M@', token)


    def test_must_provide_library_information(self):
        error = "Both library short name and secret must be specified."
        assert_raises_regexp(
            ValueError, error, self.encoder.encode, None, None, None
        )
        assert_raises_regexp(
            ValueError, error, self.encoder.encode, "A", None, None
        )
        assert_raises_regexp(
            ValueError, error, self.encoder.encode, None, "A", None
        )

    def test_cannot_encode_null_patron_identifier(self):
        assert_raises_regexp(
            ValueError, "No patron identifier specified",
            self.encoder.encode, "lib", "My library secret", None
        )

    def test_short_client_token_encode_known_value(self):
        """Verify that the encoding algorithm gives a known value on known
        input.
        """
        secret = "My library secret"
        value = self.encoder._encode(
            "a library", secret, "a patron identifier", 1234.5
        )

        # Note the colon characters that replaced the plus signs in
        # what would otherwise be normal base64 text. Similarly for
        # the semicolon which replaced the slash, and the at sign which
        # replaced the equals sign.
        eq_('a library|1234.5|a patron identifier|YoNGn7f38mF531KSWJ;o1H0Z3chbC:uTE:t7pAwqYxM@',
            value
        )

        # Dissect the known value to show how it works.
        token, signature = value.rsplit("|", 1)

        # Signature is base64-encoded in a custom way that avoids
        # triggering an Adobe bug ; token is not.
        signature = self.encoder.adobe_base64_decode(signature)

        # The token comes from the library name, the patron identifier,
        # and the time of creation.
        eq_("a library|1234.5|a patron identifier", token)

        # The signature comes from signing the token with the
        # secret associated with this library.
        key = self.encoder.signer.prepare_key(secret)
        expect_signature = self.encoder.signer.sign(token.encode("utf8"), key)
        eq_(expect_signature, signature)


class TestShortClientTokenDecoder(DatabaseTest):

    TEST_NODE_VALUE = 114740953091845

    def setup(self):
        super(TestShortClientTokenDecoder, self).setup()
        self.encoder = ShortClientTokenEncoder()
        self.decoder = ShortClientTokenDecoder(self.TEST_NODE_VALUE, [])
        self.library = self._library()
        self.library.short_name='LIBRARY'
        self.library.shared_secret='My shared secret'

    def test_uuid(self):
        u = self.decoder.uuid()
        # All UUIDs need to start with a 0 and end with the same node
        # value.
        assert u.startswith('urn:uuid:0')
        assert u.endswith('685b35c00f05')

    def test_short_client_token_lookup_delegated_patron_identifier_success(self):
        """Test that the library registry can create a
        DelegatedPatronIdentifier from a short client token generated
        by one of its libraries.
        """
        short_client_token = self.encoder.encode(
            self.library.short_name, self.library.shared_secret,
            "Foreign Patron"
        )

        identifier = self.decoder.decode(self._db, short_client_token)
        assert isinstance(identifier, DelegatedPatronIdentifier)
        eq_(self.library, identifier.library)
        eq_(DelegatedPatronIdentifier.ADOBE_ACCOUNT_ID, identifier.type)
        eq_("Foreign Patron", identifier.patron_identifier)
        assert identifier.delegated_identifier.startswith('urn:uuid:')

        # Do the lookup again and verify we get the same
        # DelegatedPatronIdentifier.
        identifier2 = self.decoder.decode(self._db, short_client_token)
        eq_(identifier, identifier2)

    def test_short_client_token_lookup_delegated_patron_identifier_failure(self):
        """Test various token decoding errors"""
        m = self.decoder._decode

        assert_raises_regexp(
            ValueError,
            'Cannot decode an empty token.',
            self.decoder.decode,
            self._db, ""
        )

        assert_raises_regexp(
            ValueError,
            'Supposed client token "no pipes" does not contain a pipe.',
            self.decoder.decode,
            self._db, "no pipes"
        )

        # A token has to contain at least two pipe characters.
        assert_raises_regexp(
            ValueError, "Invalid client token",
            m, self._db, "foo|", "signature"
        )

        # The expiration time must be numeric.
        assert_raises_regexp(
            ValueError, 'Expiration time "a time" is not numeric',
            m, self._db, "library|a time|patron", "signature"
        )

        # The patron identifier must not be blank.
        assert_raises_regexp(
            ValueError, 'Token library\|1234\| has empty patron identifier',
            m, self._db, "library|1234|", "signature"
        )

        # The library must be a known one.
        assert_raises_regexp(
            ValueError,
            'I don\'t know how to handle tokens from library "UNKNOWN"',
            m, self._db, "unknown|1234|patron", "signature"
        )

        # The token must not have expired.
        assert_raises_regexp(
            ValueError,
            'Token library\|1234\|patron expired at 2017-01-01 20:34:00',
            m, self._db, "library|1234|patron", "signature"
        )

        # (Even though the expiration number here is much higher, this
        # token is also expired, because the expiration date
        # calculation for an old-style token starts at a different
        # epoch and treats the expiration number as seconds rather
        # than minutes.)
        assert_raises_regexp(
            ValueError,
            'Token library\|1500000000\|patron expired at 2017-07-14 02:40:00',
            m, self._db, "library|1500000000|patron", "signature"
        )

        # Finally, the signature must be valid.
        assert_raises_regexp(
            ValueError, 'Invalid signature for',
            m, self._db, "library|99999999999|patron", "signature"
        )

    def test_decode_uses_adobe_base64_encoding(self):

        library = self._library()

        # The base64 encoding of this signature has a plus sign in it.
        signature = b'LbU}66%\\-4zt>R>_)\n2Q'
        encoded_signature = self.encoder.adobe_base64_encode(signature)

        # We replace the plus sign with a colon.
        assert b':' in encoded_signature
        assert b'+' not in encoded_signature

        # Make sure that decode properly reverses that change when
        # decoding the 'password'.
        def _decode(_db, token, supposed_signature):
            eq_(supposed_signature, signature)
            self.decoder.test_code_ran = True
            return "identifier", "uuid"
        self.decoder._decode = _decode

        self.decoder.test_code_ran = False

        # This username is good enough to fool
        # ShortClientDecoder._split_token, but it won't work for real.
        fake_username = "library|12345|username"
        self.decoder.decode_two_part(
            self._db, fake_username, encoded_signature
        )

        # The code in _decode_short_client_token ran. Since there was no
        # test failure, it ran successfully.
        eq_(True, self.decoder.test_code_ran)

        assert_raises_regexp(
            ValueError, "Invalid password",
            self.decoder.decode_two_part,
            self._db, fake_username, "I am not a real encoded signature"
        )
