"""
Assessment Model
===========

Class representing mindset meter assessments
"""


from google.appengine.api import search
import searchable_properties as sndb
import logging
import re

from .model import Model


def url_name_validator(property, name_str):
    """Allows lowercase letter, digits, and hyphens only. Raises Exception."""
    pattern = r'^[a-z0-9\-]+$'
    if not re.match(pattern, name_str):
        raise Exception("Invalid url name: {}".format(name_str))


class Assessment(Model):
    """A MSK representation of a mindset meter assessment, created by PERTS.

    Mostly just a name to list avaiable assessments and to organize surveys
    created from them. The bulk of the definition of an assessment happens on
    [mindsetmeter](survey.perts.net) in the form of html templates for surveys
    and reports.

    Always available to everyone, so listed by default.
    """
    name = sndb.StringProperty(required=True, search_type=search.TextField)
    # Defined on the client, but typically: self.name.lower().replace(' ', '-')
    # So for 'Growth Mindset' this is 'growth-mindset', and it's used to make
    # URLs for mindset meter, so users would be directed to
    # 'survey.perts.net/take/growth-mindset'
    url_name = sndb.StringProperty(required=True, validator=url_name_validator)
    description = sndb.TextProperty(default='', search_type=search.TextField)
    num_phases = sndb.IntegerProperty(required=True)
    listed = sndb.BooleanProperty(default=True)
