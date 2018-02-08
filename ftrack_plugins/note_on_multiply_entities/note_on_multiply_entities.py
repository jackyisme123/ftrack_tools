# :coding: utf-8
# :copyright: Copyright (c) 2017 Weta Workshop

import logging
import threading
import sys
import argparse
import json

import ftrack_api

from ftrack_action_handler.action import BaseAction


def async(fn):
    """Run *fn* asynchronously."""

    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()

    return wrapper


class NoteOnMultipleEntitiesAction(BaseAction):
    """Action to write note on multiple entities."""

    #: Action identifier.
    identifier = 'note-on-multiple-entities'

    #: Action label.
    label = 'Add Note'

    @async
    def create_notes(self, entities, text, category_id, source):
        """Create notes on *entities*."""

        # Create new session as sessions are not guaranteed to be thread-safe.
        session = ftrack_api.Session(
            auto_connect_event_hub=False, plugin_paths=[]
        )

        category = session.get('NoteCategory', category_id)
        user = session.query(
            'User where username is "{0}"'.format(source['user']['username'])
        ).one()

        logging.info('Creating notes on {0} entities'.format(len(entities)))

        job = session.create('Job', {
            'user': user,
            'status': 'running',
            'data': json.dumps({
                'description': 'Creating notes on {0} entities'.format(
                    len(entities)
                )
            })
        })

        try:
            session.commit()
        except Exception:
            session.rollback()
            raise

        try:
            for entity_type, entity_id in entities:
                entity = session.get(entity_type, entity_id)
                if category:
                    entity.create_note(
                        text, user, category=category
                    )
                else:
                    entity.create_note(text, user)
        except Exception:
            session.rollback()

            job['status'] = 'failed'

            try:
                session.commit()
            except Exception:
                session.rollback()

            raise

        job['status'] = 'done'

        try:
            session.commit()
        except Exception:
            session.rollback()
            raise

    def discover(self, session, entities, event):
        """Return true if the action is discoverable.

        Action is discoverable if all entities have a notes relationship and
        at least one entity is selected.

        """
        return (
            entities and
            all([
                entity_type in session.types and
                'notes' in session.types[entity_type].attributes.keys()
                for entity_type, entity_id in entities
            ])
        )

    def launch(self, session, entities, event):
        """Callback method for action."""
        self.logger.info(
            u'Launching action with selection {0}'.format(entities)
        )

        data = event['data']
        logging.info(u'Launching action with data: {0}'.format(data))

        if 'values' in data:
            text = data['values'].get('note_text')
            category_id = data['values'].get('note_category')
            self.create_notes(entities, text, category_id, event['source'])

        return {
            'success': True,
            'message': 'Started creating notes'
        }

    def interface(self, session, entities, event):
        """Return interface."""
        values = event['data'].get('values', {})

        if not values:
            options = [
                {'label': category['name'], 'value': category['id']}
                for category in session.query(
                    'select name, id from NoteCategory'
                )
            ]
            options.insert(0, {'label': 'None', 'value': 'auto'})
            return [
                {
                    'value': '## Writing note on **{0}** items. ##'.format(
                        len(entities)
                    ),
                    'type': 'label'
                }, {
                    'label': 'Content',
                    'name': 'note_text',
                    'value': '',
                    'type': 'textarea'
                }, {
                    'label': 'Note category',
                    'type': 'enumerator',
                    'name': 'note_category',
                    'value': 'auto',
                    'data': options
                }
            ]


def register(session, **kw):
    """Register plugin. Called when used as an plugin."""
    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an old or incompatible API and
    # return without doing anything.
    if not isinstance(session, ftrack_api.session.Session):
        return

    action_handler = NoteOnMultipleEntitiesAction(session)
    action_handler.register()


def main(arguments=None):
    """Set up logging and register action."""
    if arguments is None:
        arguments = []

    parser = argparse.ArgumentParser()
    # Allow setting of logging level from arguments.
    logging_levels = {}
    for level in (
            logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING,
            logging.ERROR, logging.CRITICAL
    ):
        logging_levels[logging.getLevelName(level).lower()] = level

    parser.add_argument(
        '-v', '--verbosity',
        help='Set the logging output verbosity.',
        choices=logging_levels.keys(),
        default='info'
    )
    namespace = parser.parse_args(arguments)

    # Set up basic logging.
    logging.basicConfig(
        format='%(asctime)s %(message)s',
        level=logging_levels[namespace.verbosity]
    )

    session = ftrack_api.Session()
    register(session)

    # Wait for events.
    logging.info(
        'Registered actions and listening for events. Use Ctrl-C to abort.'
    )
    session.event_hub.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
