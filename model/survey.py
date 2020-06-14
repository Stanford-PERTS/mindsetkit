"""
Survey Model
===========

Class representing a mindset meter survey, based on some assessment
In an entity group under the user
"""


from google.appengine.ext import ndb
import logging

from .model import Model
from .assessment import Assessment
from phrase import generate_unique_phrase
import util


class Survey(Model):
    """An instance of a mindset meter assessment, created by a user.

    Allows an MSK user to manage which surveys they've created and help them
    distribute them to participants. They are unlisted as a rule and only
    viewable by their parent users. The exception to this is finding them by
    entry code, which needs to be possible for public users. There is a
    special class method for this.

    The creating user is the "distributor" and those who take it are
    "participants". The survey consists of multiple "phases", each of which is
    a independent survey is on the [mindsetmeter app](survey.perts.net).
    """
    assessment = ndb.StringProperty(required=True)  # uid
    # Redundant with Assessment.url_name.
    url_name = ndb.StringProperty(required=True)
    group_name = ndb.StringProperty(required=True)
    entry_code = ndb.StringProperty(required=True)  # e.g. "epic shark"
    # MM1-style, to "take" each phase
    public_keys = ndb.StringProperty(repeated=True)
    # MM1-style, to see results
    private_keys = ndb.StringProperty(repeated=True)
    num_responses = ndb.IntegerProperty(repeated=True)
    auth_type = ndb.StringProperty(required=True, choices=['ids', 'initials'])

    @classmethod
    def create(klass, **kwargs):

        asmt = Assessment.get_by_id(kwargs['assessment'])
        if asmt is None:
            raise Exception("Assessment not found: {}"
                            .format(kwargs['assessment']))

        kwargs['url_name'] = asmt.url_name

        kwargs['entry_code'] = generate_unique_phrase('Survey.entry_code', n=2)

        # Generate keys for each phase.
        kwargs['private_keys'] = []
        kwargs['public_keys'] = []
        key_maker = util.Keys()
        for x in range(asmt.num_phases):
            private, public = key_maker.get_pair_as_tuple()
            kwargs['private_keys'].append(private)
            kwargs['public_keys'].append(public)

        # Blank notes for each phase.
        if 'json_properties' not in kwargs:
            kwargs['json_properties'] = {'notes': ([''] * asmt.num_phases)}

        # Start with zero responses.
        kwargs['num_responses'] = [0] * asmt.num_phases

        survey = super(klass, klass).create(**kwargs)

        return survey

    @classmethod
    def get_by_code(klass, code):
        """Get only public-safe details about a survey, accessible by anyone.

        Returns a dictionary.
        """
        survey = Survey.query(Survey.entry_code == code).get()

        if survey is None:
            return None

        to_keep = ['public_keys', 'auth_type', 'url_name']
        return {k: getattr(survey, k) for k in to_keep}

    def get_distributor(self):
        return self.key.parent().get()
