"""Collection of hard-coded settings."""

unit_test_directory = ''

session_cookie_name = ''
session_cookie_secret_key = ''

# Auth types
# * own - For those who sign in by typing in their email address and
#     password. They have a password hash. Their auth_ids look like
#     ''
# * google - For those who sign in via google. They don't have a password
#     hash; google just tells us they're legit. Their auth_ids look like
#     '', where the numbers are their google identifier.
# * facebook - Similar to google.

auth_types = ['own', 'google', 'facebook']

non_admins_can_create = ['Practice', 'Comment', 'Feedback', 'Vote', 'Survey',
                         'SurveyResult']

public_can_create = ['Feedback']

created_as_children = ['Practice', 'Comment', 'Vote', 'Survey', 'SurveyResult']

# Types of models indexed for search
indexed_models = ['Practice', 'Lesson', 'Assessment']

allowed_relationships = {
    ('Theme', 'Topic'): {'child_list': 'topics',
                         'parent_list': 'themes'},
    ('Topic', 'Lesson'): {'child_list': 'lessons',
                          'parent_list': 'topics'},
    ('Theme', 'Lesson'): {'child_list': 'popular_lessons',
                          'parent_list': 'popular_in'}
}

# Locales available
available_locales = ['en', 'es']
default_locale = 'en'

# The name of the full text search index that we maintain for content entities.
content_index = 'content_2015'

# at least 8 characters, ascii only
# http://stackoverflow.com/questions/5185326/java-script-regular-expression-for-detecting-non-ascii-characters
password_pattern = r'^[\040-\176]{8,}$'

# These domains spam us. Refuse to register users with email from these domains.
forbidden_domains = ['qq.com']

# Google sign in
google_client_id = ''
google_client_secret = ''

# Google testing sign in
google_client_id_test = ''
google_client_secret_test = ''

# Google beta sign in
google_client_id_beta = ''
google_client_secret_beta = ''

# Facebook log in
facebook_app_id = 0
facebook_app_secret = ''

# Facebook testing log in
facebook_app_id_test = 0
facebook_app_secret_test = ''

# Facebook acceptance log in
facebook_app_id_acceptance = 0
facebook_app_secret_acceptance = ''

# Mandrill SMTP API Key
mandrill_api_key = ''

# Mailchimp API Key
mailchimp_api_key = ''
mailchimp_dc = ''
# Mailchimp List number
mailchimp_list_id = ''

# We want the entity store to ignore these properties, mostly because they
# can change in ways it doesn't expect, and it shouldn't be writing to them
# anyway. These properties will be prefixed with an underscore before being
# sent to the client.
client_private_properties = [
    'modified',
    'auth_id',
]

# These properties should never be exposed to the client.
client_hidden_properties = [
    'hashed_password',
]

boolean_url_arguments = [
    'listed',
    'pending',
    'vote_for',
    'promoted',
]

integer_url_arguments = [
    'votes_for',
    'votes_against',
    'estimated_duration',
    'lesson_count',
    'min_grade',
    'max_grade',
]

# UTC timezone, in ISO date format: YYYY-MM-DD
date_url_arguments = [
    'scheduled_date',  # used in sending emails
]

# UTC timezone, in an ISO-like format (missing the 'T' character between
# date and time): YYYY-MM-DD HH:mm:SS
datetime_url_arguments = [
]

# Converted to JSON with json.dumps().
json_url_arguments = [
    'json_properties',
    'template_data',
]

list_url_arguments = [
    'tags',
    'subjects',
]

# JSON only allows strings as dictionary keys. But for these values, we want
# to interpret the keys as numbers (ints).
json_url_arguments_with_numeric_keys = [
]

# These arguments are meta-data and are never applicable to specific entities
# or api actions. They appear in url_handlers.BaseHandler.get().
ignored_url_arguments = [
    'escape_impersonation',
    'impersonate,'
]

# also, any normal url argument suffixed with _json will be interpreted as json

# Converted by util.get_request_dictionary()
# Problem: we want to be able to set null values to the server, but
# angular drops these from request strings. E.g. given {a: 1, b: null}
# angular creates the request string '?a=1'
# Solution: translate javascript nulls to a special string, which
# the server will again translate to python None. We use '__null__'
# because is more client-side-ish, given that js and JSON have a null
# value.
# javascript | request string | server
# -----------|----------------|----------
# p = null;  | ?p=__null__    | p = None
url_values = {
    '__null__': None,
}

# In URL query strings, only the string 'true' ever counts as boolean True.
true_strings = ['true']


# Email settings
#
# Platform generated emails can only be sent from email addresses that have
# viewer permissions or greater on app engine.  So if you are going to change
# this please add the sender as an application viewer on
# https://appengine.google.com/permissions?app_id=s~pegasusplatform
#
# There are other email options if this doesn't suit your needs check the
# google docs.
# https://developers.google.com/appengine/docs/python/mail/sendingmail
from_server_email_address = ''
# This address should forward to the development team
# Ben says: I could not use  directly because of
# limited permissions, so I created this gmail account which forwards all its
# mail there.
to_dev_team_email_addresses = ['', '']
# These people want to know about pratice uploads so they can manage/approve
# content.
practice_upload_recipients = [
    '',
]
# These people want to know about feedback so they can reply if needed.
feedback_recipients = [
    '',
]
# These people want to know about feedback so they can reply if needed.
comment_recipients = [
    '',
]
# * spam prevention *
# time between emails
# if we exceed this for a given to address, an error will be logged
suggested_delay_between_emails = 10      # 10 minutes
# whitelist
# some addessess we spam, like our own
# * we allow us to spam anyone at a *@perts.net domain so
# this is the best address for an admin
addresses_we_can_spam = to_dev_team_email_addresses + [
    from_server_email_address,
]
# Determines if Mandrill sends emails on local or dev environments
should_deliver_smtp_dev = False


# Redirection mapping
# @todo: Remove all of these redirects by 2018
#
# These dictionaries are used to maintain SEO 'juice' on old routes
# that are no longer active.
# See 'mindsetkit.py' for implementation

# List of special redirections for removed or relocated topics
# Format: '<topic.short_uid>': 'new route'
topic_redirection_map = {
    'about-growth-mindset-math': '/topics/about-growth-mindset',
    'teaching-growth-mindset-math': '/topics/teaching-growth-mindset',
    'celebrate-mistakes-math': '/topics/celebrate-mistakes',
}

# List of special redirections for removed or relocated 'topic/lesson's
# Format: '<topic.short_uid>/<lesson.short_uid>': 'new route'
lesson_redirection_map = {
    'about-growth-mindset-math/growth-mindset-math':
        '/practices/sW3C9WYazTictvnb',  # Forward to practice
    'about-growth-mindset-math/what-is-growth-mindset':
        '/topics/about-growth-mindset/what-is-growth-mindset',
    'about-growth-mindset-math/evidence-how-growth-mindset-leads-to-higher-achievement':
        '/topics/about-growth-mindset/evidence-how-growth-mindset-leads-to-higher-achievement',
    'about-growth-mindset-math/mindsets-can-change':
        '/topics/about-growth-mindset/mindsets-can-change',
    'teaching-growth-mindset-math/introducing-students-to-malleable-brain':
        '/topics/teaching-growth-mindset/introducing-students-to-malleable-brain',
    'teaching-growth-mindset-math/explain-neuroscience-math':
        '/topics/teaching-growth-mindset/explain-the-neuroscience',
    'teaching-growth-mindset-math/growth-mindset-lesson-plan':
        '/topics/teaching-growth-mindset/growth-mindset-lesson-plan',
    'teaching-growth-mindset-math/instilling-a-growth-mindset-takes-time':
        '/topics/teaching-growth-mindset/instilling-a-growth-mindset-takes-time',
    'celebrate-mistakes-math/growth-mindset-means-embracing-challenge-mistakes':
        '/topics/celebrate-mistakes/importance-of-mistakes',
    'celebrate-mistakes-math/make-challenge-new-comfort-zone':
        '/topics/celebrate-mistakes/make-challenge-new-comfort-zone',
    'celebrate-mistakes-math/3-ways-to-celebrate-mistakes-in-class':
        '/topics/celebrate-mistakes/3-ways-to-celebrate-mistakes-in-class',
    'celebrate-mistakes-math/give-work-encourages-mistakes-see-action':
        '/topics/celebrate-mistakes/give-work-encourages-mistakes-see-action',
    'celebrate-mistakes-math/favorite-no':
        '/topics/celebrate-mistakes/favorite-no',
    'celebrate-mistakes-math/downloadable-activity-ideas':
        '/topics/celebrate-mistakes/downloadable-activity-ideas',
    '/topics/celebrate-mistakes/favorite-no':
        '/topics/celebrate-mistakes/downloadable-activity-ideas',
}

# List of special redirections for the update Spanish parent's course
# Format: '<topic.short_uid>/<lesson.short_uid>':
#             '<new-topic.short_uid>/<new-lesson.short_uid>'
# Course short_uid is handled automatically
spanish_redirection_map = {
    'aprenda-sobre-mentalidad-en-desarrollo/que-es-una-mentalidad-en-desarrollo':
        'aprenda-sobre-mentalidad-de-crecimiento/que-es-una-mentalidad-de-crecimiento',
    'aprenda-sobre-mentalidad-en-desarrollo/reflexione-en-sus-propias-creencias':
        'aprenda-sobre-mentalidad-de-crecimiento/reflexione-en-sus-propias-creencias',
    'aprenda-sobre-mentalidad-en-desarrollo/reflexione-en-sus-propias-creencias':
        'aprenda-sobre-mentalidad-de-crecimiento/reflexione-en-sus-propias-creencias',
    'aprenda-sobre-mentalidad-en-desarrollo/lea-sobre-la-investigacion':
        'aprenda-sobre-mentalidad-de-crecimiento/lea-sobre-la-investigacion',
    'como-los-padres-pueden-transmitir-una-mentalidad-en-desarrollo/tres-maneras-transmitir':
        'como-los-padres-pueden-transmitir-una-mentalidad-de-crecimiento/tres-maneras-transmitir',
    'como-los-padres-pueden-transmitir-una-mentalidad-en-desarrollo/practique-el-proceso-del-elogio':
        'como-los-padres-pueden-transmitir-una-mentalidad-de-crecimiento/practique-el-proceso-del-elogio',
    'como-los-padres-pueden-transmitir-una-mentalidad-en-desarrollo/reflexione-sobre-fracaso':
        'como-los-padres-pueden-transmitir-una-mentalidad-de-crecimiento/reflexione-sobre-fracaso',
    'como-los-padres-pueden-transmitir-una-mentalidad-en-desarrollo/modele-cometer-errores':
        'como-los-padres-pueden-transmitir-una-mentalidad-de-crecimiento/modele-cometer-errores',
    'como-los-padres-pueden-transmitir-una-mentalidad-en-desarrollo/Utilice-el-lenguaje':
        'como-los-padres-pueden-transmitir-una-mentalidad-de-crecimiento/Utilice-el-lenguaje',
    'como-los-padres-pueden-transmitir-una-mentalidad-en-desarrollo/explique-como-la-practica':
        'como-los-padres-pueden-transmitir-una-mentalidad-de-crecimiento/explique-como-la-practica',
}
