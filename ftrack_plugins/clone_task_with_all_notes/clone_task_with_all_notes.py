import ftrack_api
import logging
import json
import argparse
import sys
import threading
import time
from ftrack_action_handler.action import BaseAction


def async(fn):
    """Run *fn* asynchronously."""

    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()

    return wrapper


class CloneTaskWithAllNotesAction(BaseAction):
    """Action to clone task with all notes."""

    #: Action identifier.
    identifier = 'clone-task-with-all-notes'

    #: Action label.
    label = 'Clone Task'

    @async
    def clone_task(self, entities, task_name, source):
        """Clone task on *entities*."""

        # Create new session as sessions are not guaranteed to be thread-safe.
        session = ftrack_api.Session(
            # server_url='http://192.168.9.82/',
            # api_key='72baaed0-1816-11e7-8c7e-005056a84326',
            # api_user='root',
            auto_connect_event_hub=False, plugin_paths=[]
        )

        user = session.query(
            'User where username is "{0}"'.format(source['user']['username'])
        ).one()

        job = session.create('Job', {
            'user': user,
            'status': 'running',
            'data': json.dumps({
                'description': 'Clone task with all notes'
            })
        })

        try:
            session.commit()
        except Exception:
            session.rollback()
            raise

        # try:
        for entity_type, entity_id in entities:
            entity = session.get(entity_type, entity_id)
        if entity['context_type'] != 'task':
            logging.info(u'Only task can be cloned')
        else:
            project = entity['parent']
            task = session.create(
                'Task', {
                    'name': task_name,
                    'task_type': entity['type'],
                    'parent': project
                }
            )
            try:
                session.commit()
            except Exception:
                session.rollback()
                job['status'] = 'failed'
                logging.info(u'task creating failed')
                session.commit()
                raise
            temp = {}
            for note in (entity['notes']):
                if note['in_reply_to_id'] == None:
                    temp[note['id']] = [note]
            for note in (entity['notes']):
                if note['in_reply_to_id'] != None:
                    temp[note['in_reply_to_id']].append(note)
            values = []
            for key,value in temp.items():
                value = sorted(value, key=lambda x : x['date'], reverse=False)
                values.append(value)
            values = sorted(values, key=lambda x : x[-1]['date'], reverse=False)
            print values
            new_notes = []
            j = 0
            for value in values:
                # task = session.query('Task where name is {0} and project.id is {1}'.format(task_name, project['id'])).one()
                note1 = value[0]
                recipients = []
                for n in note1['recipients']:
                    # print(n.keys())
                    resource = {}
                    resource['id'] = n['resource_id']
                    recipients.append(resource)
                new_note= task.create_note(
                    note1['content'], note1['author'], recipients=recipients, category=note1['category']
                )
                new_note['date'] = note1['date']
                new_notes.append(new_note)

                try:
                    session.commit()
                    time.sleep(1)
                except Exception:
                    job['status'] = 'failed'
                    session.rollback()
                    raise

            for value in values:
                for i in range(1, len(value)):
                    reply = value[i]
                    print reply['content']
                    new_reply = new_notes[j].create_reply(
                        reply['content'], reply['author']
                    )
                    new_reply['date'] = reply['date']
                j = j+1
                try:
                    session.commit()
                    time.sleep(1)
                except Exception:
                    job['status'] = 'failed'
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
            entities and len(entities) == 1 and
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
            task_name = data['values'].get('task_name')
            self.clone_task(entities, task_name, event['source'])

        return {
            'success': True,
            'message': 'Started clone task'
        }

    def interface(self, session, entities, event):
        """Return interface."""
        values = event['data'].get('values', {})

        if not values:

            return [
                {
                    'value': '## Clone task with all notes. ##',
                    'type': 'label'
                }, {
                    'label': 'New task name:',
                    'name': 'task_name',
                    'value': '',
                    'type': 'text'
                }
            ]


def register(session, **kw):
    """Register plugin. Called when used as an plugin."""
    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an old or incompatible API and
    # return without doing anything.
    if not isinstance(session, ftrack_api.session.Session):
        return

    action_handler = CloneTaskWithAllNotesAction(session)
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

    session = ftrack_api.Session(
        # server_url='http://192.168.9.82/',
        # api_key='72baaed0-1816-11e7-8c7e-005056a84326',
        # api_user='root'
    )
    register(session)

    # Wait for events.
    logging.info(
        'Registered actions and listening for events. Use Ctrl-C to abort.'
    )
    session.event_hub.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
