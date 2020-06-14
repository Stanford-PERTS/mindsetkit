"""URL Handlers are designed to be simple wrappers over our python cron module.
They generally convert a URL directly to an cron function call.
See cron.Cron
"""

from google.appengine.api import app_identity
from google.appengine.api import urlfetch
import httplib
import json
import logging
import traceback
import webapp2

from base_handler import BaseHandler
from api import (Api, PermissionDenied)
from cron import Cron
from model import (Model, User, Indexer)
import config
import test_handlers
import util


debug = util.is_development()


class CronHandler(BaseHandler):
    """Superclass for all cron-related urls."""

    def dispatch(self, *args, **kwargs):
        """Do setup for cron handlers.

        - Jsons output
        - logs exception traces
        - Initializes Api-like Cron object
        """
        # There's no true sense of a current user making a request in cron
        # jobs, so invent an admin to run them. Don't get whether they've ever
        # been created before in unique index of users, because crons run all
        # the time. The user won't be saved to the datastore anyway.
        admin_user = User.create(
            check_uniqueness=False,
            email='',
            auth_id='',
            first_name='Cron', last_name='Job', is_admin=True)

        # The testing flag allows us to use unsaved user entities to create an
        # api. Normal operation requires that the user be saved to the
        # datastore. This is the only effect; e.g. a testing api still affects
        # the datastore.
        self.api = Api(admin_user, testing=True)

        self.cron = Cron(self.api)

        self.response.headers['Content-Type'] = (
            'application/json; charset=utf-8')

        try:
            # Call the descendant handler.
            BaseHandler.dispatch(self)
            # self.write_json(self.do(*args, **kwargs))
        except Exception as error:
            trace = traceback.format_exc()
            logging.error("{}\n{}".format(error, trace))
            response = {
                'error': True,
                'message': '{}: {}'.format(error.__class__.__name__, error),
                'trace': trace,
            }
            self.response.write(json.dumps(response))

        else:
            # If everything about the request worked out, but no data was
            # returned, put out a standard empty response.
            if not self.response.body:
                self.write(None)

    def write(self, obj):
        # In the extremely common cases where we want to return an entity or
        # a list of entities, translate them to JSON-serializable dictionaries.
        if isinstance(obj, Model):
            obj = obj.to_client_dict()
        elif type(obj) is list and all([isinstance(x, Model) for x in obj]):
            obj = [x.to_client_dict() for x in obj]
        self.response.write(json.dumps({'error': False, 'data': obj}))


class CheckForErrorsHandler(CronHandler):
    """See named@errorChecker for details."""
    def get(self):
        self.write(self.cron.check_for_errors())


class CleanGcsBucketHandler(CronHandler):
    """Empties out a URL-specified GCS bucket,"""
    def get(self, bucket):
        self.write(self.cron.clean_gcs_bucket(bucket))


class SendPendingEmail(CronHandler):
    """See id_model@email for details."""
    def get(self):
        self.write(self.cron.send_pending_email())


class IndexContent(CronHandler):
    """See api.index() for details."""

    def delete(self):
        indexer = Indexer.get_or_insert('the-indexer')
        num_deleted = indexer.delete_all_content()
        self.write("Deleted {} documents from the search index."
                   .format(num_deleted))

    def get(self):
        self.write(self.cron.index())


class IndexAllContent(CronHandler):
    """See api.index_all() for details."""

    def get(self):
        num_indexed = self.cron.index_all()
        self.write("Indexed {} entities in the search index."
                   .format(num_indexed))


class AssignUsernames(CronHandler):
    """Assigns usernames to users without one"""

    def get(self):
        self.write(self.cron.assign_usernames())


class UnitTestHandler(CronHandler):
    """Runs our unit tests in production. Raises an excpetion if they fail."""
    def get(self):
        # Wrap the existing code that calls all unit tests so that an exception
        # is raised on failure.
        handler = test_handlers.AllHandler()
        response = handler.do()
        # All we care about is the 'was_successful' flag, which is only true
        # if all tests pass.
        if response['data']['was_successful']:
            self.write(None)
        else:
            raise Exception("Unit test failed in production.\n{}".format(
                response['data']))


class BackupToGcsHandler(CronHandler):
    def get(self):
        kinds = self.request.get_all('kind'),
        if not kinds:
            raise Exception("Backup handler requires kinds.")

        bucket = self.request.get('bucket', None)
        if not bucket:
            raise Exception("Backup handler requires bucket.")

        access_token, _ = app_identity.get_access_token(
            'https://www.googleapis.com/auth/datastore')
        app_id = app_identity.get_application_id()

        entity_filter = {
            'kinds': kinds,
            'namespace_ids': self.request.get_all('namespace_id')
        }
        request = {
            'project_id': app_id,
            'output_url_prefix': 'gs://{}'.format(bucket),
            'entity_filter': entity_filter
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + access_token
        }
        url = 'https://datastore.googleapis.com/v1/projects/{}:export'.format(
            app_id)

        try:
            result = urlfetch.fetch(
                url=url,
                payload=json.dumps(request),
                method=urlfetch.POST,
                deadline=60,
                headers=headers)
            if result.status_code == httplib.OK:
                logging.info(result.content)
            elif result.status_code >= 500:
                logging.error(result.content)
            else:
                logging.warning(result.content)
            self.response.status_int = result.status_code
        except urlfetch.Error:
            raise Exception('Failed to initiate export.')

        self.response.write("Export initiated.")


webapp2_config = {
    'webapp2_extras.sessions': {
        # Related to cookie security, see:
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': config.session_cookie_secret_key,
    },
}

application = webapp2.WSGIApplication([
    ('/cron/backup', BackupToGcsHandler),
    ('/cron/check_for_errors', CheckForErrorsHandler),
    ('/cron/clean_gcs_bucket/(.*)', CleanGcsBucketHandler),
    # ('/cron/run_unit_tests', UnitTestHandler),
    ('/cron/send_pending_email', SendPendingEmail),
    ('/cron/index', IndexContent),
    ('/cron/index_all', IndexAllContent),
    ('/cron/assign_usernames', AssignUsernames),
], config=webapp2_config, debug=debug)
