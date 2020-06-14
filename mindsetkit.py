from google.appengine.api import users
from google.appengine.api import users as app_engine_users
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.ext.webapp.util import run_wsgi_app
from webapp2_extras import security
from webapp2_extras import routes
from webapp2_extras.routes import RedirectRoute

import google.appengine.api.app_identity as app_identity
import cgi
import datetime
import jinja2
import json
import logging
import os
import random
# Debugging. To use, start sdk via shell and add `pdb.set_trace()` to code.
import pdb
import re
import traceback
import urllib
import webapp2
import webapp2_extras.appengine.auth.models

from api import Api, PermissionDenied
from base_handler import BaseHandler
from model import User, Practice, Theme, Topic, Lesson, ResetPasswordToken
import config
import util
import view_counter
import mandrill
import locales


# Make sure this is off in production, it exposes exception messages.
debug = util.is_development()


class MetaView(type):
    """Allows code to be run before and after get and post methods.

    See: http://stackoverflow.com/questions/6780907/python-wrap-class-method
    """

    @staticmethod
    def wrap(method):
        """Return a wrapped instance method"""

        def outer(self, *args, **kwargs):

            ## BEFORE GET ##

            # Is the user returning from a google authentication page? If so,
            # examine the credentials in their cookie and attempt to log them
            # in.
            logging.info("MetaView Outer: ".format(self.request));

            if (self.request.get('google_login') == 'true'):

                if self.get_current_user():
                    # Don't try to log someone in if they already are, just
                    # clear the URL param.
                    refresh_url = util.set_query_parameters(
                        self.request.url,
                        google_login='',
                    )
                    self.redirect(refresh_url)
                else:
                    # This will set up a redirect, so make sure to return
                    # afterwards.
                    self.handle_google_response()
                return

            ## INHERITING GET HANDLER RUNS HERE ##

            return_value = method(self, *args, **kwargs)

            ## AFTER GET ##

            # nothing here... yet...

            return return_value

        return outer

    def __new__(cls, name, bases, attrs):
        """If the class has an http GET method, wrap it."""
        if 'get' in attrs:
            attrs['get'] = cls.wrap(attrs['get'])
        return super(MetaView, cls).__new__(cls, name, bases, attrs)


class ViewHandler(BaseHandler):
    """Superclass for page-generating handlers."""

    __metaclass__ = MetaView

    def get_jinja_environment(self, template_path='templates'):
        return jinja2.Environment(
            autoescape=True,
            extensions=['jinja2.ext.autoescape'],
            loader=jinja2.FileSystemLoader(template_path),
        )

    def write(self, template_filename, template_path='templates', **kwargs):
        util.profiler.add_event("Begin ViewHandler:write")
        jinja_environment = self.get_jinja_environment(template_path)

        # Jinja environment filters:

        @jinja2.evalcontextfilter
        def jinja_json_filter(eval_context, value):
            """Seralize value as JSON and mark as safe for jinja."""
            return jinja2.Markup(json.dumps(value))

        jinja_environment.filters['to_json'] = jinja_json_filter

        def nl2br(value):
            """Replace new lines with <br> for html view"""
            return value.replace('\n', '<br>\n')

        jinja_environment.filters['nl2br'] = nl2br

        def format_datetime(value):
            # Formats datetime as Ex: "January 9, 2015"
            return '{dt:%B} {dt.day}, {dt.year}'.format(dt=value)

        jinja_environment.filters['datetime'] = format_datetime

        def format_ampescape(value):
            return value.replace('&', '%26')

        jinja_environment.filters['ampescape'] = format_ampescape

        def format_filetype(value):
            if value.split('/')[0] in ['application']:
                if value.split('/')[1] in ['pdf']:
                    formatted_type = 'pdf file'
                elif value.split('/')[1].find('wordprocessing') > -1:
                    formatted_type = 'word document'
                elif value.split('/')[1].find('presentation') > -1:
                    formatted_type = 'presentation'
                else:
                    formatted_type = 'document'
            elif value.split('/')[0] in ['image']:
                formatted_type = 'image file'
            else:
                formatted_type = value.split('/')[0]
            return formatted_type

        jinja_environment.filters['filetype'] = format_filetype

        util.profiler.add_event("Begin ViewHandler:add_jinja_filters")

        user = self.get_current_user()

        util.profiler.add_event("Begin ViewHandler:get_current_user()")

        # Only get sign in links if no user is present
        if user is None:
            # Sets up the google sign in link, used in modal on all pages,
            # which must include a special flag to alert this handler that
            # google credentials are present in the cookie. It should also
            # incorporate any redirect already set in the URL.
            redirect = str(self.request.get('redirect')) or self.request.url
            google_redirect = util.set_query_parameters(
                redirect, google_login='true')
            google_login_url = app_engine_users.create_login_url(google_redirect)
        else:
            google_login_url = ''

        util.profiler.add_event("Begin ViewHandler:get_login_redirects")

        # default parameters that all views get
        kwargs['user'] = user
        kwargs['google_login_url'] = google_login_url
        kwargs['hosting_domain'] = os.environ['HOSTING_DOMAIN']
        kwargs['share_url'] = self.request.url
        kwargs['google_client_id'] = config.google_client_id
        kwargs['server_time'] = datetime.datetime.today().replace(microsecond=0)


        util.profiler.add_event("Begin ViewHandler:set_user_params")

        # Determine which Facebook app depending on environment
        kwargs['localhost'] = False
        if util.is_localhost():
            kwargs['localhost'] = True
            kwargs['facebook_app_id'] = config.facebook_app_id_test
            kwargs['facebook_app_secret'] = config.facebook_app_secret_test
        elif os.environ['HOSTING_DOMAIN'] == 'acceptance-dot-mindsetkit.appspot.com':
            kwargs['facebook_app_id'] = config.facebook_app_id_acceptance
            kwargs['facebook_app_secret'] = config.facebook_app_secret_acceptance
        else:
            kwargs['facebook_app_id'] = config.facebook_app_id
            kwargs['facebook_app_secret'] = config.facebook_app_secret

        util.profiler.add_event("Begin ViewHandler:start_fetching_themes")

        # Fetch all themes and topics for navigation
        courses = self.api.get('Theme')
        if courses:
            # Fetch all topics for courses
            course_topic_ids = [id for course in courses for id in course.topics]
            course_topics = self.api.get_by_id(course_topic_ids)
            # Associate topics with appropriate courses
            for course in courses:
                course.associate_topics(course_topics)
                # Special case for "Teachers" kit
                if course.name == 'Growth Mindset for Teachers':
                    kwargs['teacher_topics'] = course.topics_list
        kwargs['courses'] = courses

        util.profiler.add_event("Begin ViewHandler:finish_fetching_themes")

        logging.info(util.profiler)

        # Try to load the requested template. If it doesn't exist, replace
        # it with a 404.
        try:
            template = jinja_environment.get_template(template_filename)
        except jinja2.exceptions.TemplateNotFound:
            logging.error("TemplateNotFound: {}".format(template_filename))
            return self.http_not_found()

        # Render the template with data and write it to the HTTP response.
        self.response.write(template.render(kwargs))

    def handle_google_response(self):
        """Figure out the results of the user's interaction with google.

        Attempt to login a/o register, then refresh to clear temporary url
        parameters.
        """
        logging.info("Handling a google login response.")
        error_code = None
        response = self.authenticate('google')
        logging.info("Response is: {}".format(response))
        if isinstance(response, User):
            user = response
            logging.info("User {} found, logging them in.".format(user.email))
        elif (('email_exists' in response) or
              (response == 'credentials_missing')):
            # Provide the error code to the template so the UI can advise
            # the user.
            error_code = response
        elif response == 'credentials_invalid':
            logging.info("There's no record of this google user, registering.")
            response = self.register('google')
            if isinstance(response, User):
                user = response
                logging.info("Registered {}.".format(user.email))
            else:
                # This will get written into the template, and the UI can
                # display an appropriate message.
                error_code = response
                logging.info("Error in auto-registering google user.")
        # Now that google's response has been handled, refresh the
        # request. This will create one of two behaviors:
        # * If the user was correctly logged in a/o registered, they get
        #   the requested page, ready to use, no complications, no params.
        # * If there was an error, an error code is available about why,
        #   and the url fragment/hash will trigger the login modal so a
        #   message can be displayed.
        params = {'google_login': ''}  # means remove this parameter
        new_fragment = ''  # means remove hash/fragment
        if error_code:
            logging.info("Error code: {}.".format(error_code))
            params['google_login_error'] = error_code
            new_fragment = 'login'
        refresh_url = util.set_query_parameters(
            self.request.url, new_fragment=new_fragment, **params)
        self.redirect(refresh_url)

    def dispatch(self):
        try:
            logging.info("ViewHandler.dispatch()")
            # Call the overridden dispatch(), which has the effect of running
            # the get() or post() etc. of the inheriting class.
            BaseHandler.dispatch(self)

        except Exception as error:
            trace = traceback.format_exc()
            # We don't want to tell the public about our exception messages.
            # Just provide the exception type to the client, but log the full
            # details on the server.
            logging.error("{}\n{}".format(error, trace))
            response = {
                'success': False,
                'message': error.__class__.__name__,
            }
            if debug:
                self.response.write('<pre>{}</pre>'.format(
                    traceback.format_exc()))
            else:
                self.response.write("We are having technical difficulties.")
            return

    def http_not_found(self, **kwargs):
        """Respond with a 404.

        Example use:

        class Foo(ViewHandler):
            def get(self):
                return self.http_not_found()
        """
        # default parameters that all views get
        user = self.get_current_user()

        # Sets up the google sign in link, used in modal on all pages, which
        # must include a special flag to alert this handler that google
        # credentials are present in the cookie. It should also incorporate any
        # redirect already set in the URL.
        redirect = str(self.request.get('redirect')) or self.request.url
        google_redirect = util.set_query_parameters(
            redirect, google_login='true')
        google_login_url = app_engine_users.create_login_url(google_redirect)

        kwargs['user'] = user
        kwargs['google_login_url'] = google_login_url
        kwargs['hosting_domain'] = os.environ['HOSTING_DOMAIN']
        kwargs['share_url'] = self.request.url
        kwargs['google_client_id'] = config.google_client_id

        # Determine which Facebook app depending on environment
        kwargs['localhost'] = False
        if util.is_localhost():
            kwargs['localhost'] = True
            kwargs['facebook_app_id'] = config.facebook_app_id_test
            kwargs['facebook_app_secret'] = config.facebook_app_secret_test
        elif os.environ['HOSTING_DOMAIN'] == 'acceptance-dot-mindsetkit.appspot.com':
            kwargs['facebook_app_id'] = config.facebook_app_id_acceptance
            kwargs['facebook_app_secret'] = config.facebook_app_secret_acceptance
        else:
            kwargs['facebook_app_id'] = config.facebook_app_id
            kwargs['facebook_app_secret'] = config.facebook_app_secret

        # Fetch all themes and topics for navigation
        courses = self.api.get('Theme')
        if courses:
            # fetch topics for each theme
            course_topic_ids = [id for course in courses for id in course.topics]
            course_topics = self.api.get_by_id(course_topic_ids)
            # associate topics with appropriate courses
            for course in courses:
                course.associate_topics(course_topics)
                # Special case for "Teachers" kit
                if course.name == 'Growth Mindset for Teachers':
                    kwargs['teacher_topics'] = course.topics_list
        kwargs['courses'] = courses

        self.error(404)
        jinja_environment = self.get_jinja_environment()
        template = jinja_environment.get_template('404.html')
        self.response.write(template.render(kwargs))

    def head(self, **kwargs):
        # You're not supposed to give a message body to HEAD calls
        # http://stackoverflow.com/questions/1501573/when-should-i-be-responding-to-http-head-requests-on-my-website
        self.response.clear()

    def options(self, **kwargs):
        # OPTION Response based on ->
        # http://zacstewart.com/2012/04/14/http-options-method.html
        self.response.set_status(200)
        self.response.headers['Allow'] = 'GET,HEAD,OPTIONS'


class Logout(ViewHandler):
    """Clears the user's session, closes connections to google."""
    def get(self):
        self.log_out()

        redirect = self.request.get('redirect') or '/'

        if util.is_localhost():
            # In the SDK, it makes sense to log the current user out of Google
            # entirely (otherwise admins have to click logout twice, b/c
            # existing code will attempt to sign them right in again).
            self.redirect(app_engine_users.create_logout_url(redirect))
        else:
            # In production, we don't want to sign users out of their Google
            # account entirely, because that would break their gmail, youtube,
            # etc. etc. Instead, just clear the cookies on *this* domain that
            # Google creates. That's what self.log_out() does above. So we're
            # done, except for a simple redirect.
            self.redirect(redirect)


class UnitTests(ViewHandler):
    def get(self):
        # @todo: read contents of unit test directory
        r = re.compile(r'^test_(\S+)\.py$')
        test_files = filter(lambda f: r.match(f), os.listdir('unit_testing'))
        test_suites = [r.match(f).group(1) for f in test_files]
        self.write('test.html', test_suites=test_suites)


class AboutPage(ViewHandler):

    def get(self):
        self.write(
            'about.html',
        )


class Admin(ViewHandler):

    def get(self):
        if self.get_current_user().is_admin:
            self.write(
                'admin.html',
            )
        else:
            self.redirect('/')


class LandingPage(ViewHandler):

    def get(self):
        self.write(
            'main.html',
        )


class UserPage(ViewHandler):

    def get(self, username=None):
        if username is None:
            if self.get_current_user():
                self.write(
                    'profile.html',
                    your_profile=True,
                    profile_user=self.get_current_user(),
                    profile_user_json=json.dumps(self.get_current_user().to_client_dict()),
                )
            else:
                self.redirect('/')
        else:
            users = self.api.get('User', canonical_username=username)
            if users:
                profile_user = users[0]
                your_profile = (profile_user is self.get_current_user())
                self.write(
                    'profile.html',
                    your_profile=your_profile,
                    profile_user=profile_user,
                    profile_user_json=json.dumps(profile_user.to_client_dict()),
                )
            else:
                return self.http_not_found()


class ResetPasswordPage(ViewHandler):

    def get(self, token):
        user = ResetPasswordToken.get_user_from_token_string(token)
        valid = user is not None
        self.write('reset_password.html', token=token, valid=valid)


class UnsubscribePage(ViewHandler):
    """Redirect page for email unsubscribe from Mandrill service"""

    def get(self):
        # Variables passed through to resubscribe button
        md_id = self.request.get('md_id')
        md_email = self.request.get('md_email')

        self.write(
            'unsubscribe.html',
            md_id=md_id,
            md_email=md_email,
        )


class ResubscribePage(ViewHandler):
    """Resubscribes a user to the email list

    Needs to be manually performed,
    So we ping Matt. Obviously."""

    def get(self):
        md_id = self.request.get('md_id')
        md_email = self.request.get('md_email')

        mandrill.send(
            to_address=config.from_server_email_address,
            subject="Please Re-subscribe!",
            body=(
                "&#128007; Heyo,<br><br>Someone requested they be "
                "re-subscribed to the MSK mailing list. We have to do this "
                "manually. Here's their info.<br><br><b>Email:</b> {}<br>"
                "<b>ID:</b> {}<br><br>Thanks!!"
                .format(md_email, md_id)
            ),
        )

        self.write(
            'resubscribe.html',
        )


class PracticeHomePage(ViewHandler):

    def get(self):
        self.redirect('/search', permanent=True)


class SearchPage(ViewHandler):

    def get(self):
        self.write(
            'search.html',
        )

class BelongingResources(ViewHandler):

    def get(self):
        self.redirect(
            '/search?tags=Belonging'
        )


class PracticePage(ViewHandler):

    def get(self, practice_id):
        id = Practice.get_long_uid(practice_id)
        practice = self.api.get_by_id(id)
        if practice:
            # Increment view counts on the practice
            view_counter.increment(id)

            # Get related practices
            related_practices = Practice.get_related_practices(practice, 3)

            # Get color from associated content
            color = '#51516c'  # default color
            if practice.associated_content:
                associated_content = self.api.get_by_id(practice.associated_content)
                color = associated_content.color

            creator = practice.key.parent().get()
            self.write(
                'practice.html',
                practice=practice,
                creator=creator,
                creator_json=json.dumps(creator.to_client_dict()),
                color=color,
                related_practices=related_practices,
            )
        else:
            # 404 if theme cannot be found
            return self.http_not_found()


class UploadPage(ViewHandler):

    def get(self, practice_id=None):
        user = self.get_current_user()

        if user is None:
            self.redirect('/search')
            return

        # Check if user is practice creator or admin
        if not user.is_admin and practice_id:
            practice = self.api.get_by_id(Practice.get_long_uid(practice_id))
            creator = practice.key.parent().get()
            if creator is not user:
                self.redirect('/practices/{}'.format(practice_id))

        self.write(
            'practice-upload.html',
            practice_id=practice_id,
        )


class MindsetMeter(ViewHandler):
    def get(self):
        self.write('mindsetmeter_distributor.html')


class EnterSurvey(ViewHandler):
    def get(self):
        self.write('enter_survey.html')


class SurveyInstructions(ViewHandler):
    def get(self, survey_id):
        survey = self.api.get_by_id(survey_id)
        template = 'instructions_{}.html'.format(survey.auth_type)
        self.write(template, survey=survey.to_client_dict())


class ThemeHandler(ViewHandler):

    def get(self, theme_id):
        id = Theme.get_long_uid(theme_id)
        theme = self.api.get_by_id(id)
        first_lesson_link = ''
        if theme is not None:
            # fetch topics for theme
            topics = []
            if theme.topics:
                topics = self.api.get_by_id(theme.topics)
                # fetch lessons for each topic
                topic_lesson_ids = [id for topic in topics for id in topic.lessons]
                theme_lessons = self.api.get_by_id(topic_lesson_ids)
                # associate lessons with appropriate topics
                for topic in topics:
                    topic.lessons_list = [l for l in theme_lessons if l.uid in topic.lessons]

                # get first lesson for CTA
                first_lesson_link = '/{}'.format(theme.short_uid)
                has_first_lesson = topics[0] and topics[0].lessons_list and topics[0].lessons_list[0]
                if has_first_lesson:
                    first_lesson_link = '/{}/{}/{}'.format(
                        first_lesson_link,
                        topics[0].short_uid,
                        topics[0].lessons_list[0].short_uid)

            # Get related practices
            related_practices = Practice.get_related_practices(theme, 6)

            # Get translated text and locale
            if theme.locale in config.available_locales:
                locale = theme.locale
            else:
                locale = default_locale

            self.write(
                'theme.html',
                theme=theme,
                topics=topics,
                first_lesson_link=first_lesson_link,
                audience=theme.target_audience,
                related_practices=related_practices,
                locale=locale,
                translation=locales.translations[locale]["courses"],
            )
        else:
            # Special (temporary) redirect for math kit
            # Consider adding 'aliases' for themes
            if theme_id == 'math':
                self.redirect('/growth-mindset-math', permanent=True)
            # 404 if theme cannot be found
            return self.http_not_found()

    def head(self, theme_id):
        # Include an override here to not confuse bad subdirectories as 200 OK
        id = Theme.get_long_uid(theme_id)
        theme = self.api.get_by_id(id)
        if theme is not None:
            self.response.clear()
        else:
            self.error(404)

    def options(self, theme_id):
        # Include an override here to not confuse bad subdirectories as 200 OK
        id = Theme.get_long_uid(theme_id)
        theme = self.api.get_by_id(id)
        if theme is not None:
            self.response.set_status(200)
            self.response.headers['Allow'] = 'GET,HEAD,OPTIONS'
        else:
            self.error(404)


class OldThemeHandler(ViewHandler):
    """Redirects old themes to landing page"""

    def get(self, theme_id):
        self.redirect('/', permanent=True)


class OldSpanishThemeHandler(ViewHandler):
    """Redirects old spanish theme to new one"""

    def get(self, theme_id):
        self.redirect('/mentalidad-de-crecimiento-padres', permanent=True)


class TopicHandler(ViewHandler):

    def get(self, topic_id):
        full_topic_id = Topic.get_long_uid(topic_id)
        topic = self.api.get_by_id(full_topic_id)

        # check all content objects were found
        if topic is not None:

            # Increment view counts on the topic
            view_counter.increment(full_topic_id)

            # find lessons in topic
            lessons = []
            if topic.lessons:
                lessons = self.api.get_by_id(topic.lessons)

            # Get related practices
            related_practices = Practice.get_related_practices(topic, 6)

            self.write(
                'topic.html',
                topic=topic,
                lessons=lessons,
                color=topic.color,
                related_practices=related_practices,
            )

        else:
            # 404 if topic cannot be found
            return self.http_not_found()


class ThemeTopicHandler(ViewHandler):
    """Redirects theme topics to theme page with # navigation"""

    def get(self, theme_id, topic_id):
        # Redirects now to theme.
        self.redirect('/{}#{}'.format(theme_id, topic_id), permanent=True)


class OldTopicHandler(ViewHandler):
    """Redirects [math or teachers] theme topics to new routes"""

    def get(self, theme_id, topic_id):
        if topic_id in config.topic_redirection_map:
            # Redirect to new location
            self.redirect(
                config.topic_redirection_map[topic_id],
                permanent=True)
        else:
            self.redirect('/topics/{}'.format(topic_id), permanent=True)


class LessonHandler(ViewHandler):

    def get(self, theme_id, topic_id, lesson_id):
        full_lesson_id = Lesson.get_long_uid(lesson_id)
        lesson = self.api.get_by_id(full_lesson_id)

        full_theme_id = Theme.get_long_uid(theme_id)
        theme = self.api.get_by_id(full_theme_id)

        full_topic_id = Topic.get_long_uid(topic_id)
        topic = self.api.get_by_id(full_topic_id)

        # check all content objects were found
        if lesson is not None and topic is not None and theme is not None:

            # Increment view counts on the lesson
            view_counter.increment(full_lesson_id)
            view_counter.increment('{}:{}:{}'.format(
                full_theme_id, full_topic_id, full_lesson_id))

            # Get other topics in theme for navigating
            topics = []
            if theme.topics:
                topics = self.api.get_by_id(theme.topics)

            # get other lessons in topic for navigating
            lessons = []
            # first check for bad topic--lesson match
            if topic.lessons:
                lessons = self.api.get_by_id(topic.lessons)

                # get lesson index and previous and next lessons
                lesson_index = 0
                topic_index = 0
                if topic.uid in theme.topics:
                    topic_index = theme.topics.index(topic.uid)
                if lesson.uid in topic.lessons:
                    lesson_index = topic.lessons.index(lesson.uid)

                # get next lesson from current or next topic
                next_lesson = ''
                next_lesson_url = ''
                next_topic = ''
                next_topic_url = ''
                next_url = ''
                if lesson_index < len(lessons) - 1:
                    next_lesson = lessons[lesson_index + 1]
                    next_lesson_url = '/{}/{}/{}'.format(
                        theme.short_uid, topic.short_uid, next_lesson.short_uid)
                    next_url = next_lesson_url
                elif topic_index < len(theme.topics) - 1:
                    next_topic = topics[topic_index + 1]
                    next_topic_url = '/{}/{}'.format(
                        theme.short_uid, next_topic.short_uid)
                    next_url = next_topic_url

            # Get translated text and locale
            if theme.locale in config.available_locales:
                locale = theme.locale
            else:
                locale = config.default_locale

            if os.path.isfile('templates/lessons/' + lesson.short_uid + '.html'):
                self.write(
                    '/lessons/{}.html'.format(lesson.short_uid),
                    theme=theme,
                    topic=topic,
                    lesson=lesson,
                    lessons=lessons,
                    lesson_index=lesson_index,
                    next_lesson=next_lesson,
                    next_lesson_url=next_lesson_url,
                    next_topic=next_topic,
                    next_topic_url=next_topic_url,
                    next_url=next_url,
                    color=topic.color,
                    audience=theme.target_audience,
                    locale=locale,
                    translation=locales.translations[locale]["lessons"],
                )
            else:
                # 404 if lesson html cannot be found
                return self.http_not_found()

        else:
            # 404 if lesson cannot be found
            return self.http_not_found()


class TopicLessonHandler(ViewHandler):

    def get(self, topic_id, lesson_id):
        full_lesson_id = Lesson.get_long_uid(lesson_id)
        lesson = self.api.get_by_id(full_lesson_id)

        full_topic_id = Topic.get_long_uid(topic_id)
        topic = self.api.get_by_id(full_topic_id)

        # check all content objects were found
        if not (lesson is None or topic is None):

            # Increment view counts on the lesson
            view_counter.increment(full_lesson_id)
            view_counter.increment(
                '{}:{}'.format(full_topic_id, full_lesson_id))

            theme = self.api.get_by_id(topic.themes[0])
            # Determines if current theme is for Teachers or not
            # 'teacher_theme' variable affects the UI
            teacher_theme = (theme.short_uid in ['growth-mindset', 'growth-mindset-teachers'])

            # Get related practices
            related_practices = Practice.get_related_practices(topic, 4)

            # get other lessons in topic for navigating
            lessons = []
            # first check for bad topic--lesson match
            if topic.lessons:
                lessons = self.api.get_by_id(topic.lessons)

                # get lesson index and previous and next lessons
                lesson_index = 0
                if lesson.uid in topic.lessons:
                    lesson_index = topic.lessons.index(lesson.uid)

                next_topic = ''
                related_topics = []

                # get next lesson from current or next topic
                next_lesson = ''
                next_lesson_url = ''
                next_url = ''
                if lesson_index < len(lessons) - 1:
                    next_lesson = lessons[lesson_index + 1]
                    next_lesson_url = '/topics/{}/{}'.format(
                        topic.short_uid, next_lesson.short_uid)
                    next_url = next_lesson_url
                else:
                    # fetch next topic for final lesson
                    topic_index = 0
                    if topic.uid in theme.topics:
                        topic_index = theme.topics.index(topic.uid)
                    if topic_index < len(theme.topics) - 1:
                        next_topic = self.api.get_by_id(theme.topics[topic_index + 1])
                        next_url = '/topics/{}'.format(next_topic.short_uid)

                    # get list of 3 other topics
                    related_topic_ids = []
                    for idx, val in enumerate(theme.topics):
                        if next_topic:
                            if val != topic.uid and val != next_topic.uid:
                                related_topic_ids.append(val)
                        elif val != topic.uid:
                            related_topic_ids.append(val)
                    if related_topic_ids:
                        related_topics = self.api.get_by_id(related_topic_ids)
                        if len(related_topics) >= 3:
                            related_topics = random.sample(related_topics, 3)

            # All topic lessons use default locale
            locale = config.default_locale

            if os.path.isfile('templates/lessons/' + lesson.short_uid + '.html'):
                self.write(

                    '/lessons/{}.html'.format(lesson.short_uid),
                    theme=theme,
                    teacher_theme=teacher_theme,
                    topic=topic,
                    lesson=lesson,
                    lessons=lessons,
                    lesson_index=lesson_index,
                    next_lesson=next_lesson,
                    next_lesson_url=next_lesson_url,
                    next_url=next_url,
                    next_topic=next_topic,
                    color=topic.color,
                    related_topics=related_topics,
                    related_practices=related_practices,
                    locale=locale,
                    translation=locales.translations[locale]["lessons"],
                )
            else:
                # 404 if lesson html cannot be found
                return self.http_not_found()

        else:
            # 404 if lesson cannot be found
            return self.http_not_found()


class OldLessonHandler(ViewHandler):
    """Redirects old lesson routes in 'math' and 'teachers' theme"""

    def get(self, theme_id, topic_id, lesson_id):
        topic_lesson = '{}/{}'.format(topic_id, lesson_id)
        if topic_lesson in config.lesson_redirection_map:
            # Redirect to new location
            self.redirect(
                config.lesson_redirection_map[topic_lesson],
                permanent=True)
        else:
            self.redirect('/topics/{}/{}'.format(topic_id, lesson_id), permanent=True)


class OldSpanishLessonHandler(ViewHandler):
    """Redirects old lesson routes in 'math' and 'teachers' theme"""

    def get(self, theme_id, topic_id, lesson_id):
        topic_lesson = '{}/{}'.format(topic_id, lesson_id)
        if topic_lesson in config.spanish_redirection_map:
            # Redirect to new location
            self.redirect(
                '/mentalidad-de-crecimiento-padres/{}'.format(
                    config.spanish_redirection_map[topic_lesson]),
                permanent=True)
        else:
            self.redirect('/mentalidad-de-crecimiento-padres', permanent=True)


webapp2_config = {
    'webapp2_extras.sessions': {
        # Related to cookie security, see:
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': config.session_cookie_secret_key,
    },
}


class MSKRoute(RedirectRoute):
    """Route subclass that defaults to strict_slash=True
    to automatically redirect urls ending with '/'
    to their equivalent without

    https://webapp-improved.appspot.com/api/webapp2_extras/routes.html
    """
    def __init__(self, template, handler, strict_slash=True, name=None,
                 **kwargs):

        # Routes with 'strict_slash=True' must have a name
        if strict_slash and name is None:
            # Set a name from the template
            # ** Be sure this isn't creating duplicate errors
            # ** but 'template' should be unique so I think it's good.
            name = template

        return super(MSKRoute, self).__init__(
            template, handler=handler, strict_slash=strict_slash, name=name,
            **kwargs
        )


application = webapp2.WSGIApplication([
    MSKRoute('/logout', Logout),
    MSKRoute('/admin/test', UnitTests),
    MSKRoute('/about', AboutPage),
    MSKRoute('/admin', Admin),
    MSKRoute('/', LandingPage),
    MSKRoute('/profile', UserPage),
    MSKRoute('/users/<username>', UserPage),
    MSKRoute('/reset_password/<token>', ResetPasswordPage),
    MSKRoute('/unsubscribe', UnsubscribePage),
    MSKRoute('/resubscribe', ResubscribePage),
    MSKRoute('/practices', PracticeHomePage),
    MSKRoute('/search', SearchPage),
    MSKRoute('/practices/upload', UploadPage),
    MSKRoute('/practices/edit/<practice_id>', UploadPage),
    MSKRoute('/practices/<practice_id>', PracticePage),
    MSKRoute('/mindsetmeter', MindsetMeter),
    MSKRoute('/mindsetmeter/enter', EnterSurvey),
    MSKRoute('/go', EnterSurvey),
    MSKRoute('/mindsetmeter/instructions/<survey_id>', SurveyInstructions),
    MSKRoute('/topics/<topic_id>', TopicHandler),
    MSKRoute('/topics/<topic_id>/<lesson_id>', TopicLessonHandler),
    # Redirects from old lessons in teacher and math themes
    MSKRoute('/<theme_id:growth-mindset(\-math)?>/<topic_id>/<lesson_id>', OldLessonHandler),
    # Redirects from old spanish theme lessons to new ones
    MSKRoute('/<theme_id:mentalidad-en-desarrollo-padres>/<topic_id>/<lesson_id>', OldSpanishLessonHandler),
    MSKRoute('/<theme_id>/<topic_id>/<lesson_id>', LessonHandler),
    # Redirects from old topics in teacher and math themes
    MSKRoute('/<theme_id:growth-mindset(\-math)?>/<topic_id>', OldTopicHandler),
    MSKRoute('/<theme_id>/<topic_id>', ThemeTopicHandler),
    # Redirects from old teacher and math themes
    MSKRoute('/<theme_id:growth-mindset(\-math)?>', OldThemeHandler),
    # Redirects from old spanish themes
    MSKRoute('/<theme_id:mentalidad-en-desarrollo-padres>', OldSpanishThemeHandler),
    MSKRoute('/<theme_id>', ThemeHandler),
], config=webapp2_config, debug=True)
