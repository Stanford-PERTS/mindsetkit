"""
Survey Result Model
===========

Class representing an MSK user's response to a single mindset meter survey
In an entity group under the user
"""


from google.appengine.ext import ndb
import logging

from .model import Model


class SurveyResult(Model):
    """Stores keys to individual mindset meter results. Child of user."""
    # MM1-style, to look up MM1 results, also the name of MM1 result groups.
    private_key = ndb.StringProperty(required=True)
    public_key = ndb.StringProperty(required=True)
    # Redundant value from Assessment.name
    assessment_name = ndb.StringProperty(required=True)
    # Redundant value from Survey.group_name
    group_name = ndb.StringProperty(required=True)
    distributor = ndb.StringProperty(required=True)  # uid
    phase = ndb.IntegerProperty(required=True)
