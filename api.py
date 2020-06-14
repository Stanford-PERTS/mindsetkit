"""API Layer

Most interaction with the Datastore also happens through these functions. This
is where permissions are enforced. Expect calls to raise exceptions if things
go wrong.
"""

from google.appengine.api import search
from google.appengine.ext import ndb
import datetime  # for checking reset password tokens
import logging
import markdown
import re

from model import (Model, Content, Theme, Topic, Lesson, User, Practice,
                   Comment, Vote, ResetPasswordToken, Assessment, Survey,
                   SurveyResult)
import config
import util


class PermissionDenied(Exception):
    pass


class DuplicateEmail(Exception):
    """Invalid kwarg provided"""
    pass


class InvalidUsername(Exception):
    """Invalid kwarg provided"""
    pass


class DuplicateUsername(Exception):
    """Invalid kwarg provided"""
    pass


class Api:
    """The set of functions through which the outside world interacts with
    the Mindset Kit.

    Designed to be instantiated in the context of a user. Who the user is
    and what relationships they have determine how permissions are enforced.
    """

    def __init__(self, user=None, testing=False):
        """Construct an interface. Enforces user sign in.

        Args:
            user: mixed, model.User who is making the api request or None if
                no user is signed in (generally referred to as 'public').
            testing: bool, allow use of unsaved user entities to create an api;
                normal operation requires that the user be saved to the
                datastore. This is the only effect; e.g. a testing api still
                affects the datastore.
        """
        if user and not testing:
            # Make sure the user is real.
            logging.info("Init with user: {}".format(user))
            user = user.key.get()
            if not user or not isinstance(user, User):
                raise PermissionDenied(
                    "Api could not be initialized. User {} not found."
                    .format(user))
        self.user = user

    @classmethod
    def post_process(klass, results, unsafe_filters):
        """Assumes IN filters with list values, e.g. {'id', ['X', 'Y']}."""
        logging.info(u'Api.post_process() handled unsafe filters:')
        logging.info(u'{}'.format(unsafe_filters))
        all_matching_sets = []
        for k, v in unsafe_filters.items():
            matches = set([e for e in results if getattr(e, k) in v])
            all_matching_sets.append(matches)
        return set.intersection(*all_matching_sets)

    @classmethod
    def limit_subqueries(klass, filters):
        # GAE limits us to 30 subqueries! This is a BIG problem, because
        # stacking 'property IN list' filters MULTIPLIES the number of
        # subqueries (since IN is shorthand for a bunch of = comparisions). My
        # temporary solution is to detect unwieldy queries and do some post-
        # processing in python.
        # https://groups.google.com/forum/#!topic/google-appengine-python/ZlqZHwfznbQ
        subqueries = 1
        safe_filters = {}
        unsafe_filters = {}
        in_filters = {}
        for k, v in filters.items():
            if type(v) is list:
                subqueries *= len(v)
                in_filters[k] = v
            else:
                safe_filters[k] = v
        if subqueries > 30:
            # mark in_filters as unsafe one by one, starting with the largest,
            # until subqueries is small enough
            s = subqueries
            for k, v in sorted(in_filters.items(), key=lambda f: len(f[1]),
                            reverse=True):
                if s < 30:
                    safe_filters[k] = v
                else:
                    unsafe_filters[k] = v
                s /= len(v)
        else:
            safe_filters.update(in_filters)
        if len(unsafe_filters) > 0:
            logging.info(u'Api.limit_subqueries() marked filters as unsafe '
                         'because they would generate too many subqueries:')
            logging.info(u'{}'.format(unsafe_filters))
        return (safe_filters, unsafe_filters)

    @ndb.transactional(xg=True)
    def associate(self, parent, child, position=None):
        """For example, adding a topic to a theme, or a lesson to a topic.

        Considers that the child may be newly-created, i.e. not yet saved to
        the datastore. Parent entities must always have been saved previously.

        Updates within a transaction to prevent other processes from corrupting
        association lists. Must be a cross-group transaction (xg=True) because
        it writes to two root entities, which are two separate groups: the
        parent and the child.

        Args:
            parent: a Theme or Topic entity (must have been saved previously)
            child: a Topic or Lesson entity (possibly unsaved)
            position: a counting-from-zero index of where the child should be
                relative to other children of the parent.
        """
        if not self.user or not self.user.is_admin:
            raise PermissionDenied("Only admins can associate.")

        logging.info(u'Api.associate(parent={}, child={}, position={})'
                     .format(parent, child, position))

        parent_kind = Model.get_kind(parent)
        child_kind = Model.get_kind(child)
        relationship = (parent_kind, child_kind)
        if relationship not in config.allowed_relationships:
            raise Exception("Cannot associate {} to {}."
                            .format(child_kind, parent_kind))

        # Do a key fetch so we can guarantee we start with an accurate copy of
        # each entity.
        parent = parent.key.get()
        fetched_child = child.key.get()

        # If the child has never been saved before (i.e. we're in the middle
        # a create request), getting it by uid will return None. In that case,
        # we shouldn't save the modified child. Some later process will do so.
        if fetched_child is None:
            should_save_child = False
        else:
            should_save_child = True
            # If the fetched child exists, it represents a more up-to-date
            # copy, and we should use it rather than what was passed in.
            child = fetched_child

        prop_info = config.allowed_relationships[relationship]
        child_list = getattr(parent, prop_info['child_list'])
        parent_list = getattr(child, prop_info['parent_list'])

        if child.uid in child_list:
            raise Exception("Child {} is already associated with parent {}. "
                            "To change child's position, update the parent."
                            .format(child, parent))
        # Check for position. If None, add child to end of list.
        if position is None:
            child_list.append(child.uid)
        else:
            child_list.insert(position, child.uid)
        parent_list = list(set(parent_list + [parent.uid]))

        setattr(parent, prop_info['child_list'], child_list)
        setattr(child, prop_info['parent_list'], parent_list)

        parent.put()
        if should_save_child:
            child.put()

        return (parent, child)

    def check_reset_password_token(self, token_id):
        """Validate a token supplied by a user.

        Returns the matching user entity if the token is valid.
        Return None if the token doesn't exist or has expired.
        """
        token_entity = ResetPasswordToken.get_by_id(token_id)

        if token_entity is None:
            # This token doesn't exist. The provided token string is invalid.
            return None

        # Check that it hasn't expired and isn't deleted
        one_hour = datetime.timedelta(hours=1)
        expired = datetime.datetime.now() - token_entity.created > one_hour
        if expired or token_entity.deleted:
            # Token is invalid.
            return None

        return User.get_by_id(token_entity.user_id)

    def clear_reset_password_tokens(self, user_id):
        """Delete all tokens for a given user."""
        query = ResetPasswordToken.query(
            ResetPasswordToken.deleted == False,
            ResetPasswordToken.user_id == user_id,
        )

        tokens_to_put = []
        for token in query:
            token.deleted = True
            tokens_to_put.append(token)
        ndb.put_multi(tokens_to_put)

    def create(self, kind, **kwargs):
        """Create an entity, following conventions and relationships."""

        if self.user:
            if not self.user.is_admin and kind not in config.non_admins_can_create:
                raise PermissionDenied("Non-admins cannot create {}".format(kind))
        elif kind not in config.public_can_create:
                raise PermissionDenied("Public cannot create.")

        logging.info(u'Api.create(kind={}, kwargs={})'.format(kind, kwargs))

        klass = Model.get_class(kind)

        # Some entities require association immediately upon creation.
        if kind in ['Topic', 'Lesson']:
            # The parameters 'parent' and 'position' are relevant to the
            # associate function, but will confuse ndb. Remove them before
            # creating the new entity.
            parent = position = None
            if 'parent' in kwargs:
                parent = kwargs['parent']
                del kwargs['parent']
            # Alternatively accept parent uid
            elif 'parent_uid' in kwargs:
                parent = self.get_by_id(kwargs['parent_uid'])
                del kwargs['parent_uid']
            if 'position' in kwargs:
                position = kwargs['position']
                del kwargs['position']
            entity = klass.create(**kwargs)
            if parent is not None:
                parent, entity = self.associate(parent, entity, position)
        # Other entities require a parent entity to be specified.
        elif kind in config.created_as_children:
            # For these types, 'parent' is in a Datastore sense; votes,
            # comments and practices are created in entity groups with users as
            # parents. When a normal user creates these, assume that the parent
            # is the creating user. But when an admin creates them, allow the
            # parent to be specified.
            if not self.user.is_admin and 'parent' in kwargs:
                raise PermissionDenied("Non-admins cannot specify parents.")
            if 'parent' not in kwargs:
                kwargs['parent'] = self.user
            entity = klass.create(**kwargs)
        # Others require nothing special.
        else:
            entity = klass.create(**kwargs)

        # now we're done, so we can put all the changes to the new entity
        entity.put()

        return entity

    def delete(self, id):
        if not self.user:
            raise PermissionDenied("Public cannot delete.")

        logging.info(u'Api.delete(id={})'.format(id))

        entity = Model.get_by_id(id)
        if not self.user.is_admin:
            # Then the user must be the creator of the thing, which equates
            # to being the parent entity (in a Datastore sense) of the thing
            # being deleted.
            if entity.key.parent() != self.user.key:
                raise PermissionDenied(
                    "{} does not own {} and may not delete it."
                    .format(self.user, entity))

        entity.deleted = True
        # We're about to take it out of the index, so don't bother updating
        # it with the new value of the deleted property.
        # See model.Model._post_put_hook()
        entity.forbid_post_put_hook = True
        entity.put()

        if isinstance(entity, (Lesson, Practice)):
            logging.info("Removing soft-deleted content from search.")
            search.Index(config.content_index).delete(entity.uid)

        entity_kind = Model.get_kind(entity)

        # If User object, need to remove unique properties from unique model
        if entity_kind is 'User':
            entity.remove_unique_properties(entity)

        # If vote, need to decrement vote on subject object
        if entity_kind is 'Vote':
            if entity.practice_id:
                practice_id = entity.practice_id
                practice = Practice.get_by_id(practice_id)
                if practice is not None:
                    practice.votes_for -= 1
                    practice.put()
            if entity.lesson_id:
                lesson_id = entity.lesson_id
                lesson = Lesson.get_by_id(lesson_id)
                if lesson is not None:
                    lesson.votes_for -= 1
                    lesson.put()

    def delete_everything(self):
        if not (self.user and self.user.is_admin and util.is_localhost()):
            raise PermissionDenied("Only admins working on a localhost "
                                   "server can delete everything.")
        util.delete_everything()
        util.delete_all_in_index(config.content_index)

    def get(self, kind, ancestor=None, **kwargs):
        """Query entities in the datastore.

        Makes either strongly consistent or eventually consistent queries based
        on the supplied parameters.

        Getting entities with a specific user as ancestor (see
        config.created_as_children for a complete list) is strongly consistent.

        Everything else is eventually consistent, e.g. searching for practices
        with the tag 'mindset'.
        """
        logging.info(u'Api.get(kind={}, kwargs={}, ancestor={})'
                     .format(kind, kwargs, ancestor))

        klass = Model.get_class(kind)

        if ancestor:
            if not self.user:
                raise PermissionDenied("Public cannot run ancestor queries.")
            elif not self.user.is_admin and ancestor != self.user:
                raise PermissionDenied(
                    "Users can only run ancestor queries on themselves.")
            query = klass.query(klass.deleted == False, ancestor=ancestor.key)
        else:
            # If this isn't an ancestor query, we only want to show listed
            # entities.
            if self.user and self.user.is_admin:
                query = klass.query(klass.deleted == False)
            # Handles fact that users have no 'listed' field
            elif kind == 'User':
                query = klass.query(klass.deleted == False)
            else:
                query = klass.query(klass.deleted == False,
                                    klass.listed == True)

        if 'n' in kwargs:
            if not self.user:
                raise PermissionDenied("Public cannot change result set size.")
            n = int(kwargs['n'])
            del kwargs['n']
        else:
            # Speedy and simple by default. If you want more, specify n!
            n = 20

        if 'order' in kwargs:
            # Uses '-' in order to indicate reverse direction,
            # otherwise standard sorting is used
            if '-' in kwargs['order']:
                kwargs['order'] = kwargs['order'].replace('-', '')
                query = query.order(-getattr(klass, kwargs['order']))
            else:
                query = query.order(getattr(klass, kwargs['order']))
            del kwargs['order']

        # Pagination using a 'page' argument pulls n arguments offset by n*page
        # pull first set of results with page=0
        if 'page' in kwargs:
            offset = int(kwargs['page']) * n
            del kwargs['page']
        else:
            offset = 0

        # Now that all the non-standard kwargs have been removed (n, order...)
        # we process all the rest as parameters/filters on the query.

        safe_kwargs, unsafe_kwargs = Api.limit_subqueries(kwargs)

        for k, v in safe_kwargs.items():
            if type(v) is list:
                query = query.filter(getattr(klass, k).IN(v))
            else:
                query = query.filter(getattr(klass, k) == v)

        results = query.fetch(n, offset=offset)

        # post-processing, if necessary
        if len(unsafe_kwargs) > 0:
            results = Api.post_process(results, unsafe_kwargs)

        return results

    def get_by_id(self, id_or_ids):
        """Strongly consistent key fetch, available to anyone, even public."""
        # The only exception is that deleted entries are never returned.
        result = Model.get_by_id(id_or_ids)
        if type(result) is list:
            return [e for e in result if e is not None and not e.deleted]
        else:
            return None if not result or result.deleted else result

    @ndb.transactional(xg=True)
    def disassociate(self, parent, child):
        """Remove relationship between content entities.

        Updates within a transaction to prevent other processes from corrupting
        association lists. Must be a cross-group transaction (xg=True) because
        it writes to two root entities, which are two separate groups: the
        parent and the child.

        Args:
            parent: a Theme or Topic entity
            child: a Topic or Lesson entity
        """
        if not self.user or not self.user.is_admin:
            raise PermissionDenied("Only admins may disassociate.")

        logging.info(
            'Api.disassociate(parent={}, child={})'
            .format(parent, child))

        parent = parent.key.get()
        child = child.key.get()

        parent_kind = Model.get_kind(parent)
        child_kind = Model.get_kind(child)
        relationship = (parent_kind, child_kind)
        prop_info = config.allowed_relationships[relationship]

        child_list = getattr(parent, prop_info['child_list'])
        parent_list = getattr(child, prop_info['parent_list'])

        if child.uid in child_list:
            child_list.remove(child.uid)
        if parent.uid in parent_list:
            parent_list.remove(parent.uid)
        # Temporarily added to remove bad associations moving forward
        if child.uid in parent_list:
            parent_list.remove(child.uid)

        setattr(parent, prop_info['child_list'], child_list)
        setattr(child, prop_info['parent_list'], parent_list)

        parent.put()
        child.put()

        return (parent, child)

    def reorder(self, parent, child, move_up=True):
        """Reorders a child entity in a content entity.

        Args:
            parent: a Theme or Topic entity
            child: a Topic or Lesson entity
        """

        if not self.user or not self.user.is_admin:
            raise PermissionDenied("Only admins may reorder.")

        logging.info(
            'Api.reorder(parent={}, child={}, move_up={})'
            .format(parent, child, move_up))

        parent = parent.key.get()
        child = child.key.get()

        parent_kind = Model.get_kind(parent)
        child_kind = Model.get_kind(child)
        relationship = (parent_kind, child_kind)
        prop_info = config.allowed_relationships[relationship]
        child_list = getattr(parent, prop_info['child_list'])

        # Checks for child in child_list and interprets the variable
        # 'move_up' to determine new position in the list
        if child.uid in child_list:
            position = child_list.index(child.uid)
            if move_up in ("yes", "true", "t", "1"):
                new_position = position - 1
            else:
                new_position = position + 1
            child_list.remove(child.uid)
            child_list.insert(new_position, child.uid)

        setattr(parent, prop_info['child_list'], child_list)
        parent.put()

        return parent

    def _stringify_search_params(self, params):
        """Turn the various tags, toggles, and search text a user specifies in
        the UI into a string the search API understands.

        Within a tag type, specified values are joined with OR, while multiple
        tag types are joined with AND. Search text goes at end with no field
        specified, so it functions as full-text search (implicitly treated as
        AND with the field-specific tags)

        Example query string:
        (tags:foo OR tags:bar) AND (subjects:Math OR subjects:Economics) my search
        """
        # Don't create side effects on the dictionary passed in.
        params = params.copy()

        query_string = ''  # final string to submit to search API
        type_strings = []  # e.g. '(tag:foo OR tag:bar)'

        # Everything except the "plain" search text needs to be labeled with
        # a field, so take it out and process the rest.
        query_string += params.pop('q', '')

        # Removes bad characters from the string using regex
        query_string = re.sub('[(){}<>]', '', query_string)

        query_string = query_string.replace(' ', ' AND ')

        # Max and min grades are handled separately because they're turned into
        # inequalities.
        min_grade = params.pop('min_grade', None)
        max_grade = params.pop('max_grade', None)

        # Test for overlap between the search requested and the max/min of
        # the content we've got.
        if min_grade is not None:
            type_strings.append('max_grade >= {}'.format(min_grade))
        if max_grade is not None:
            type_strings.append('min_grade <= {}'.format(max_grade))

        for field_name in params:
            # Make everything else a list.
            values = params[field_name]
            if type(values) is not list:
                values = [values]
            if len(values) > 0:  # protect against empty lists
                value_strings = []  # e.g. 'tag:foo'
                for value in values:
                    formatted_value = '\"' + value.lower() + '\"'
                    value_strings.append(field_name + ': ' + formatted_value)
                type_strings.append('(' + ' OR '.join(value_strings) + ')')

        query_string = ' AND '.join(type_strings) + ' ' + query_string

        logging.info("Searching for:")
        logging.info(query_string)

        return query_string

    def _annotate_search_content(self, result_dicts):
        """Add data re: content authors and current user to search results."""

        # Content authors

        content_keys = [Model.id_to_key(d['uid']) for d in result_dicts]
        parent_ids = [k.parent().id() for k in content_keys if k.parent()]
        # A single datastore read for all parents.
        parents = self.get_by_id(parent_ids) or []

        # Votes and comments by the current user (who may not be signed in).

        if self.user:
            users_votes_for = self.get('Vote', ancestor=self.user)
            content_user_voted_for = ([v.lesson_id for v in users_votes_for] +
                                      [v.practice_id for v in users_votes_for])
            users_comments = self.get('Comment', ancestor=self.user)
            content_user_commented = ([c.lesson_id for c in users_comments] +
                                      [c.practice_id for c in users_comments])
        else:
            # The user is not signed in.
            content_user_voted_for = []
            content_user_commented = []

        # Loop through search results and modify.

        for d in result_dicts:
            # Find and add content authors.
            for p in parents:
                # I don't love this way of testing if a user is a parent of a
                # given content entity, b/c it relies on our uid conventions,
                # but it's awfully convenient.
                if p.uid in d['uid']:
                    d['user'] = p.to_client_dict()
            # Check if the current user voted for or commented on this.
            if d['uid'] in content_user_voted_for:
                d['user_voted_for'] = True
            if d['uid'] in content_user_commented:
                d['user_commented_on'] = True

            # Add in short_uid if not
            if 'short_uid' not in d:
                d['short_uid'] = Practice.convert_uid(d['uid'])

        return result_dicts

    def search_content(self, params):
        index = search.Index(config.content_index)
        search_text = ''

        # This search_results objects has properties `number_found`, `results`,
        # and `cursor`. See
        # https://cloud.google.com/appengine/docs/python/search/searchresultsclass
        # search.Query docs:
        # https://cloud.google.com/appengine/docs/python/search/queryclass
        # search.QueryOptions docs:
        # https://cloud.google.com/appengine/docs/python/search/queryoptionsclass

        # Pagination using a 'page' argument pulls n arguments offset by n*page
        # pull first set of results with page=0
        page_size = 20
        offset = 0
        if 'page' in params:
            offset = int(params.pop('page')) * page_size

        # Build the SortOptions with 2 sort keys
        sort1 = search.SortExpression(expression='promoted', direction=search.SortExpression.DESCENDING, default_value='A')
        sort2 = search.SortExpression(expression='created', direction=search.SortExpression.DESCENDING, default_value=0)
        sort_opts = search.SortOptions(expressions=[sort1, sort2])

        search_results = index.search(search.Query(
            query_string=self._stringify_search_params(params),
            options=search.QueryOptions(
                limit=page_size,
                offset=offset,
                snippeted_fields=['summary', 'body'],
                sort_options= sort_opts,
            )
        ))
        result_dicts = [util.search_document_to_dict(doc)
                        for doc in search_results.results]

        result_dicts = self._annotate_search_content(result_dicts)

        return result_dicts

    def update(self, id, **kwargs):
        if not self.user:
            raise PermissionDenied("Public cannot update.")

        logging.info(u'Api.update(id={}, kwargs={})'.format(id, kwargs))

        entity = Model.get_by_id(id)
        if not self.user.is_admin:
            # Then the user must be the creator of the thing, which equates
            # to being the parent entity (in a Datastore sense) of the thing
            # being deleted. Or, of course, the user can update themselves.
            if entity.key.parent() != self.user.key and entity != self.user:
                raise PermissionDenied(
                    "{} does not own {} and may not write to it."
                    .format(self.user, entity))

        # Updating passwords is not straight-forward assignment; they have to
        # be hashed, emails sent, etc. Process them separately.
        if 'password' in kwargs:
            entity.set_password(kwargs.pop('password'))  # we can assume a User

        entity_kind = Model.get_kind(entity)

        # Checks for user validations (could be moved to User model)
        if entity_kind is 'User':
            will_update_email = False
            will_update_username = False

            if 'email' in kwargs and kwargs['email'] != entity.email:
                # check if email is unique
                if not entity.check_email_uniqueness(kwargs['email']):
                    raise DuplicateEmail("There is already a user with email {}."
                                         .format(kwargs['email']))
                else:
                    will_update_email = True

            if 'username' in kwargs and kwargs['username'] != entity.username:
                # check if username is valid
                if entity.is_valid_username(kwargs['username']):
                    raise InvalidUsername("Invalid username {}. Use only letters, numbers, dashes, and underscores."
                                          .format(kwargs['username']))

                # check if username is unique
                if not entity.check_username_uniqueness(kwargs['username']):
                    raise DuplicateUsername("There is already a user with username {}."
                                            .format(kwargs['username']))
                else:
                    will_update_username = True

            # Assuming all else is good, delete old Unique username and email
            # Need to make sure nothing wrong first, so not to accidentally
            # remove any Unique objects in use without an actual update.
            if will_update_email:
                email = kwargs.pop('email', '')
                entity.update_email(email)

            if will_update_username:
                username = kwargs.pop('username', '')
                entity.update_username(username)

            # Handle Mailchimp subscription updating
            if 'receives_updates' in kwargs and kwargs['receives_updates'] is not entity.receives_updates:
                should_subscribe = kwargs['receives_updates']
                User.set_subscription(entity.email, should_subscribe)

        # Determine if user should be notified regarding practice
        elif entity_kind is 'Practice':
            entity.check_status_update(**kwargs)

        # Everything else is just a property of the entity.
        for k, v in kwargs.items():
            setattr(entity, k, v)

        entity.put()
        return entity

    def populate(self, n=None):
        """Generate fake data for unit testing and load testing.

        Checks for the existence of user  before running,
        so it essentially can't be run twice without clearing the datastore.

        TODO: use the n parameter to allow this script to create arbitrarily
        large sets of data.
        """
        if not self.user or not self.user.is_admin:
            raise PermissionDenied("Only admins may populate.")

        # Since we know this is being run by an admin, use their existing api
        # to create stuff admins would normally create.
        admin_api = self

        # Generate a fake user to create other stuff.
        normal_user = admin_api.create(
            'User', email='',
            auth_id='',
            last_name='Doe', first_name='John')

        normal_api = Api(normal_user)

        theme = admin_api.create(
            'Theme',
            id='listed-theme-1',
            name=u'List\xebd Theme 1', summary=u"R\xf8ckin'",
            json_properties=u'{"a": "\xeb", "b":[1,2,3]}', listed=True)

        topic = admin_api.create(
            'Topic',
            id='listed-topic-1',
            parent=theme, position=1, name=u'List\xebd Topic 1',
            summary=u"R\xf8ckin'",
            json_properties={'a': u'\xeb', 'b': [1, 2, 3]}, listed=True)

        lesson = admin_api.create(
            'Lesson',
            id='listed-lesson-1',
            parent=topic, position=1, name=u'List\xebd Lesson 1',
            summary=u"R\xf8ckin'",
            tags=['tagone', 'tagtwo'],
            min_grade=5,
            max_grade=8,
            subjects=['reading', 'writing'],
            json_properties={'a': u'\xeb', 'b': [1, 2, 3]}, listed=True)

        practice = normal_api.create(
            'Practice',
            name=u'List\xebd Practice 1',
            summary=u"R\xf8ckin'",
            tags=['super', u'c\xf8\xf8l', 'tagone'],
            subjects=['math', 'history', 'reading'],
            min_grade=0,
            max_grade=13,
            type='text',
            body=u"R\xf8ckin'",
            youtube_id='https://www.youtube.com/watch?v=6sJqTDaOrTg',
            has_files=True,
            pending=False,
            listed=True,
        )

        comment = normal_api.create(
            'Comment',
            body=u"R\xf8ckin'",
            practice_id=practice.uid,
            lesson_id=lesson.uid,
        )

        assessment = admin_api.create(
            'Assessment',
            name=u"MM2 Demo",
            url_name='mm2-demo',
            description=u"R\xf8ckin'",
            num_phases=2,
        )

        survey = normal_api.create(
            'Survey',
            assessment=assessment.uid,
            group_name=u"G\xebography 101",
            auth_type='initials',
            json_properties={"notes": [u"R\xf8ckin'", "the FREE world"]},
        )

        # # These are designed to be created from a cross-domain call, so there
        # # won't be a normal user api available.
        # survey_result = admin_api.create(
        #     'SurveyResult',
        #     private_key='tbd',  # todo: port MM1 hashing code
        #     public_key='tbd',  # todo: port MM1 hashing code
        #     assessment_name=u"List\xebd Assessment 1",
        #     group_name=u"G\xebography 101",
        #     distributor=normal_user.uid,
        #     phase=1,
        # )

        # Return everything that was created, in case someone wants to use it,
        # e.g. unit tests.
        return (normal_user, theme, topic, lesson, practice, comment,
                assessment, survey)
                # assessment, survey, survey_result)
