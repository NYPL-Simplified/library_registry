"""
Tests for the Resource, Hyperlink, and Validation models.
"""
from datetime import datetime, timedelta

import pytest

from library_registry.model import (Validation)


class TestResourceModel:
    """
    The Resource model is currently simple enough that it doesn't need unit tests.
    """


class TestHyperlinkModel:
    @pytest.mark.skip(reason="TODO")
    def test_notify_exit_early(self, db_session, create_test_resource, create_test_library, create_test_hyperlink):
        """
        GIVEN: A Hyperlink object
        WHEN:  .notify() is called on that object and any of the following is true:
                 - The emailer passed to the function is invalid
                 - The url_for function passed to the function is invalid
                 - The object does not have an associated Library
                 - The object does not have an associated Resource
        THEN:  The function should exit before doing any work
        """

    @pytest.mark.skip(reason="TODO")
    def test_notify(self):
        """
        GIVEN:
        WHEN:
        THEN:
        """


@pytest.fixture(scope="function")
def validation_obj(db_session, create_test_resource, create_test_validation):
    r = create_test_resource(db_session)
    v = create_test_validation(db_session, r)
    yield v
    db_session.delete(v)
    db_session.delete(r)
    db_session.commit()


class TestValidationModel:
    def test_restart(self, db_session, create_test_resource, create_test_validation):
        """
        GIVEN: A Validation object
        WHEN:  The .restart() method is called on that object
        THEN:  The validation's started_at time should be reset to now, its secret to a new secret,
               and its success to False
        """

    def test_mark_as_successful(self, validation_obj):
        """
        GIVEN: A Validation object which has not been marked successful and has not expired
        WHEN:  .mark_as_successful() is called on that object
        THEN:  The value of .secret should be set to None, and .success to True
        """
        assert validation_obj.secret is not None
        assert validation_obj.success is not True
        validation_obj.mark_as_successful()
        assert validation_obj.secret is None
        assert validation_obj.success is True

    def test_mark_as_successful_raises_exceptions(self, validation_obj):
        """
        GIVEN: A Validation object which has succeeded or expired
        WHEN:  .mark_as_successful() is called on that object
        THEN:  An Exception should be raised
        """
        validation_obj.success = True

        with pytest.raises(Exception):
            validation_obj.mark_as_successful()

        validation_obj.success = False
        validation_obj.started_at = datetime.utcnow() - timedelta(days=10)

        with pytest.raises(Exception):
            validation_obj.mark_as_successful()

    def test_deadline_property(self, validation_obj):
        """
        GIVEN: A Validation object whose 'success' attribute does not evaluate to True
        WHEN:  That object's .deadline property is accessed
        THEN:  A datetime should be returned that is one day past the Validation's started_at time
        """
        started_at_value = datetime.utcnow()
        expected = started_at_value + Validation.EXPIRES_AFTER
        validation_obj.started_at = started_at_value

        assert validation_obj.deadline == expected

    def test_deadline_property_success_true(self, validation_obj):
        """
        GIVEN: A Validation object whose 'success' attribute does evaluate to True
        WHEN:  That object's .deadline property is accessed
        THEN:  None should be returned
        """
        validation_obj.success = True
        assert validation_obj.deadline is None

    def test_active_property(self, validation_obj):
        """
        GIVEN: A Validation object which is not yet successful and also not expired
        WHEN:  That object's .active property is accessed
        THEN:  True should be returned
        """
        assert validation_obj.active is True         # Success is false, expiry still in future

        validation_obj.success = True
        assert validation_obj.active is False        # Success is now true, so not active

        validation_obj.success = False
        validation_obj.started_at = datetime.utcnow() - timedelta(days=10)
        assert validation_obj.active is False        # Success is false, but expiry has passed
