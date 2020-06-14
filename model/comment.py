"""
Comment Model
===========

Model for commenting on Practices and Lessons;
Always in a group under a user
"""

import logging
import os
import re

import config
import util
import mandrill
import searchable_properties as sndb

from .lesson import Lesson
from .model import Model
from .practice import Practice
from .theme import Theme
from .topic import Topic
from .email import Email
from .user import User


class Comment(Model):
    """Always in a group under a User."""

    body = sndb.TextProperty(default='')
    practice_id = sndb.StringProperty(default=None)
    lesson_id = sndb.StringProperty(default=None)
    # Overrides Model's default for this property, which is False. We always
    # want to see comments.
    listed = sndb.BooleanProperty(default=True)

    @classmethod
    def create(klass, **kwargs):
        if ('practice_id' not in kwargs) and ('lesson_id' not in kwargs):
            raise Exception('Must specify either a practice or a lesson when '
                            'creating a comment. Received kwargs: {}'
                            .format(kwargs))
        comment = super(klass, klass).create(**kwargs)

        # For email notifications
        content_url = '/'
        content = None

        # Increment num_comments on Practice or Lesson if success
        if comment.practice_id:
            practice = Practice.get_by_id(comment.practice_id)
            if practice is not None:
                practice.num_comments += 1
                practice.put()

                # For email
                content = practice
                content_url = '/practices/{}'.format(practice.short_uid)

                # Send email to creator
                creator = practice.get_parent_user()
                commenter = comment.get_parent_user()

                # logic to not email yourself...
                if creator.email != commenter.email:

                    short_name = creator.first_name or ''
                    full_name = creator.full_name
                    commenter_image_url = commenter.profile_image

                    # Uses Email model to queue email and prevent spam
                    email = Email.create(
                        to_address=creator.email,
                        subject="Someone commented on your Mindset Kit upload",
                        template="comment_creator_notification.html",
                        template_data={'short_name': short_name,
                                       'full_name': full_name,
                                       'commenter_name': commenter.full_name,
                                       'commenter_image_url': commenter_image_url,
                                       'content_name': content.name,
                                       'comment_body': comment.body,
                                       'content_url': content_url,
                                       'domain': os.environ['HOSTING_DOMAIN']},
                    )

                    email.put()

                # Send email to any users @replied to
                usernames = re.search('\@(\w+)', comment.body)

                if usernames is not None:
                    username = usernames.group(0).split('@')[1]

                    # Fetch user from username and send email message
                    replied_to = User.query(User.username == username).fetch(1)
                    if replied_to:
                        replied_to = replied_to[0]

                        short_name = replied_to.first_name or ''
                        full_name = replied_to.full_name
                        commenter_image_url = commenter.profile_image

                        # Uses Email model to queue email and prevent spam
                        email = Email.create(
                            to_address=replied_to.email,
                            subject="Someone replied to you on Mindset Kit",
                            template="comment_reply_notification.html",
                            template_data={
                                'short_name': short_name,
                                'full_name': full_name,
                                'commenter_name': commenter.full_name,
                                'commenter_image_url': commenter_image_url,
                                'content_name': content.name,
                                'comment_body': comment.body,
                                'content_url': content_url,
                                'domain': os.environ['HOSTING_DOMAIN']
                            },
                        )

                        email.put()

        if comment.lesson_id:
            lesson = Lesson.get_by_id(comment.lesson_id)
            if lesson is not None:
                lesson.num_comments += 1
                lesson.put()
                content = lesson

                # Get first url for lesson for emailing
                topics = Topic.get_by_id(lesson.topics)
                theme = [theme for topic in topics for theme in topic.themes][0]
                lesson_theme = Theme.get_by_id(theme)
                content_url = '/' + lesson_theme.short_uid + '/' + topics[0].short_uid + '/' + lesson.short_uid

        # Email interested team members that a comment has been created
        mandrill.send(
            to_address=config.comment_recipients,
            subject="New Comment on Mindset Kit!",
            template="comment_notification.html",
            template_data={'comment': comment,
                           'user': comment.get_parent_user(),
                           'content': content,
                           'content_url': content_url,
                           'domain': os.environ['HOSTING_DOMAIN']},
        )

        logging.info('model.Comment queueing an email to: {}'
                     .format(config.comment_recipients))

        return comment

    @classmethod
    def convert_uid(klass, short_or_long_uid):
        """Changes long-form uid's to short ones, and vice versa.

        Overrides method provided in Model.

        Long form example: Practice_Pb4g9gus.User_oha4tp8a
        Short form exmaple: Pb4g9gusoha4tp8a
        """
        if '.' in short_or_long_uid:
            parts = short_or_long_uid.split('.')
            return ''.join([x.split('_')[1] for x in parts])
        else:
            return 'Comment_{}.User_{}'.format(
                short_or_long_uid[:8], short_or_long_uid[8:])

    def parent_user_id(self):
        return self.key.parent().id()

    def get_parent_user(self):
        return self.key.parent().get()