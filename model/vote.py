"""
Vote Model
===========

Indicates votes for Lesson and Practice objects
Always in a group under a User
"""

import os
import logging

import config
import util
import mandrill
import searchable_properties as sndb

from .lesson import Lesson
from .model import Model
from .practice import Practice


class Vote(Model):
    """Always in a group under a User."""

    vote_for = sndb.BooleanProperty(default=True)
    practice_id = sndb.StringProperty(default=None)
    lesson_id = sndb.StringProperty(default=None)

    @classmethod
    def create(klass, **kwargs):
        if ('practice_id' not in kwargs) and ('lesson_id' not in kwargs):
            raise Exception('Must specify either a practice or a lesson when '
                            'creating a vote. Received kwargs: {}'
                            .format(kwargs))
        # Check if user has voted on this entity
        # existing_vote = klass.query(klass.deleted == False, ancestor=**kwargs['parent'].key, )
        # if existing_vote:
        #     raise Exception('Found an existing vote on this entity for '
        #                     'current user. Received kwargs: {}'
        #                     .format(kwargs))

        # Replace lesson_id and practice_id with full versions
        if 'practice_id' in kwargs:
            kwargs[u'practice_id'] = Practice.get_long_uid(kwargs[u'practice_id'])
        if 'lesson_id' in kwargs:
            kwargs[u'lesson_id'] = Lesson.get_long_uid(kwargs[u'lesson_id'])

        vote = super(klass, klass).create(**kwargs)

        # Increment votes_for on Practice or Lesson if success
        if vote.practice_id:
            practice = Practice.get_by_id(vote.practice_id)
            if practice is not None:
                practice.votes_for += 1
                practice.put()
        if vote.lesson_id:
            lesson = Lesson.get_by_id(vote.lesson_id)
            if lesson is not None:
                lesson.votes_for += 1
                lesson.put()

        return vote

    def parent_user_id(self):
        return self.key.parent().id()