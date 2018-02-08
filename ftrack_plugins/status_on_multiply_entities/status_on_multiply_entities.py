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


class StatusOnMultipleEntitiesAction(BaseAction):
    """Action to write note on multiple entities."""

    #: Action identifier.
    identifier = 'status-on-multiple-entities'

    #: Action label.
    label = 'Change Status'

    @async
    def change_statuses(self, entities, category_id, source):
        """Change statuses on *entities*."""

        # Create new session as sessions are not guaranteed to be thread-safe.
        session = ftrack_api.Session(
            auto_connect_event_hub=False, plugin_paths=[]
        )

        # Get entity category from the first entity
        first_entity = session.get(entities[0][0], entities[0][1])
        # First entity type is task or milestone
        if first_entity.entity_type != 'AssetVersion':
            if first_entity['ancestors']:
                project_schema = first_entity['ancestors'][0]['parent']['project_schema']
            else:
                project_schema = first_entity['parent']['project_schema']
            task_category = project_schema.get_statuses(first_entity['object_type']['name'])
        # First entity type is version
        else:
            link_type = first_entity['link'][0]['type']
            link_id = first_entity['link'][0]['id']
            link_project = session.query('{0} where id is {1}'.format(link_type, link_id)).one()
            task_category = link_project['project_schema'].get_statuses(first_entity.entity_type)

        # Get target category from provided id
        for cat in task_category:
            if cat['id'] == category_id:
                category = cat
                break

        # Run job as current user
        user = session.query(
            'User where username is "{0}"'.format(source['user']['username'])
        ).one()

        logging.info('Change statuses on {0} entities'.format(len(entities)))

        job = session.create('Job', {
            'user': user,
            'status': 'running',
            'data': json.dumps({
                'description': 'Changing statuses on {0} entities'.format(
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
                    entity['status'] = category
                else:
                    logging.critical(
                        'Category provided could not be matched with a valid category for the first entity'
                    )
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

        Action is discoverable if all entities are either Tasks, Milestones or Versions and
        have have a status.

        """
        first_entity = session.get(entities[0][0], entities[0][1])
        if first_entity.entity_type != 'AssetVersion':
            for entity_type, entity_id in entities:
                entity = session.get(entity_type, entity_id)
                if entity['object_type']['name'] != 'Task' and entity['object_type']['name'] != 'Milestone':
                    return False
                elif entity['object_type'] != first_entity['object_type']:
                    return False
                elif entity_type not in session.types:
                    return False
                elif 'status' not in session.types[entity_type].attributes.keys():
                    return False
        return True

    def launch(self, session, entities, event):
        """Callback method for action."""
        self.logger.info(
            u'Launching action with selection {0}'.format(entities)
        )

        data = event['data']
        logging.info(u'Launching action with data: {0}'.format(data))

        if 'values' in data:
            category_id = data['values'].get('status_category')
            self.change_statuses(entities, category_id, event['source'])

        return {
            'success': True,
            'message': 'Started changing statuses'
        }

    def interface(self, session, entities, event):
        """Return interface."""
        values = event['data'].get('values', {})
        entity_id = entities[0][1]
        entity_type = entities[0][0]
        entity = session.get(entity_type, entity_id)
        if entity.entity_type != 'AssetVersion':
            if entity['ancestors']:
                project_schema = entity['ancestors'][0]['parent']['project_schema']
            else:
                project_schema = entity['parent']['project_schema']
            if not values:
                options = [
                    {'label': category['name'], 'value': category['id']}
                    for category in project_schema.get_statuses(entity['object_type']['name'])
                ]
                return [
                    {
                        'value': '## Changing statuses on **{0}** items. ##'.format(
                            len(entities)
                        ),
                        'type': 'label'
                    }, {
                        'label': 'Status category',
                        'type': 'enumerator',
                        'name': 'status_category',
                        'value': 'Select One',
                        'data': options
                    }
                ]
        else:
            link_type = entity['link'][0]['type']
            link_id = entity['link'][0]['id']
            link_project = session.query('{0} where id is {1}'.format(link_type, link_id)).one()
            if not values:
                options = [
                    {'label': category['name'], 'value': category['id']}
                    for category in link_project['project_schema'].get_statuses(entity.entity_type)
                ]
                return [
                    {
                        'value': '## Changing statuses on **{0}** items. ##'.format(
                            len(entities)
                        ),
                        'type': 'label'
                    }, {
                        'label': 'Status category',
                        'type': 'enumerator',
                        'name': 'status_category',
                        'value': 'Select One',
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

    action_handler = StatusOnMultipleEntitiesAction(session)
    action_handler.register()


def main(arguments=None):
    """Set up logging and register action."""
    if arguments is None:
        arguments = []

    parser = argparse.ArgumentParser()
    # Allow setting of logging level from arguments.

    log_levels = {}
    for level in (
            logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING,
            logging.ERROR, logging.CRITICAL
    ):
        log_levels[logging.getLevelName(level).lower()] = level

    parser.add_argument(
        '-v', '--verbosity',
        help='Set the logging output verbosity.',
        choices=log_levels.keys(),
        default='info'
    )
    namespace = parser.parse_args(arguments)

    # Set up basic logging.
    logging.basicConfig(
        format='%(asctime)s %(message)s',
        level=log_levels[namespace.verbosity]
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
