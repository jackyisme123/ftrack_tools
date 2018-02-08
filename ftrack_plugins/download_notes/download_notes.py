# :coding: utf-8
# :copyright: Copyright (c) 2017 Weta Workshop

import logging
import threading
import sys
import argparse
import json
import unicodecsv as csv
import arrow
import collections
import ftrack_api
import os

from ftrack_action_handler.action import BaseAction
import smtplib

# Import the email modules we'll need
import email
import email.mime.application


def async(fn):
    """Run *fn* asynchronously."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


class DownloadNoteOnSingleEntityAction(BaseAction):
    """Action to write note on multiple entities."""

    #: Action identifier.
    identifier = 'notes-download-on-single-entity'

    #: Action label.
    label = 'Download Notes'

    @staticmethod
    def send_mail(_from, _to, subject, text, filename, file_type, server):
        """send mail function"""
        msg = email.mime.Multipart.MIMEMultipart()
        msg['From'] = _from
        msg['To'] = _to
        msg['Subject'] = subject
        body = email.mime.Text.MIMEText(text)
        msg.attach(body)
        fp = open(filename, 'rb')
        att = email.mime.application.MIMEApplication(fp.read(),_subtype=file_type)
        fp.close()
        att.add_header('Content-Disposition','attachment;filename={0}'.format(filename))
        msg.attach(att)
        server = smtplib.SMTP(server)
        server.sendmail(_from, [_to], msg.as_string())
        server.quit()

    @async
    def download_notes(self, entities, category_id, source):
        """Create notes on *entities*."""

        # Create new session as sessions are not guaranteed to be thread-safe.
        session = ftrack_api.Session(
            auto_connect_event_hub=False, plugin_paths=[]
        )
        # Get category name
        if category_id != 'all' and category_id != 'Select One' :
            category = session.get('NoteCategory', category_id)
            category_name = category['name']
        else:
            category_name = 'all'

        user = session.query(
            'User where username is "{0}"'.format(source['user']['username'])
        ).one()

        logging.info('Download notes on single entity')

        job = session.create('Job', {
            'user': user,
            'status': 'running',
            'data': json.dumps({
                'description': 'Download notes on single entity'
            })
        })

        try:
            session.commit()
        except Exception:
            session.rollback()
            raise

        try:
            # sort all notes from action entity and its decedents
            for entity_type, entity_id in entities:
                entity = session.get(entity_type, entity_id)
                all_notes = []
                for entity_note in entity['notes']:
                    all_notes.append(entity_note)
                for asset in entity['assets']:
                    for version in asset['versions']:
                        for version_note in version['notes']:
                            all_notes.append(version_note)
                for descendant in entity['descendants']:
                    for descendant_note in descendant['notes']:
                        all_notes.append(descendant_note)
                    for descendant_asset in descendant['assets']:
                        for descendant_version in descendant_asset['versions']:
                            for descendant_version_note in descendant_version['notes']:
                                all_notes.append(descendant_version_note)
                all_notes = sorted(all_notes, key=lambda x : x['date'], reverse=False)
                # put notes in a ordered dictionary
                result = collections.OrderedDict()
                category_name1 = 'Default'
                if len(all_notes) != 0:
                    if category_id == 'all' or category_id == 'Select One':
                        for note in all_notes:
                            if not note['in_reply_to_id']:
                                if note['category']:
                                    category_name1 = note['category']['name']
                                info = {
                                    'full_name': note['author']['first_name']+' '+note['author']['last_name'],
                                    'date': note['date'].format('YYYY-MM-DD HH-mm-ss'),
                                    'content': note['content'],
                                    'category': category_name1
                                }
                                result[note['id']] = [info]
                        for key in result.keys():
                            for note in all_notes:
                                if note['in_reply_to_id'] == key:
                                    if note['category']:
                                        category_name1 = note['category']['name']
                                    info = {
                                        'full_name': note['author']['first_name']+' '+note['author']['last_name'],
                                        'date': note['date'].format('YYYY-MM-DD HH-mm-ss'),
                                        'content': note['content'],
                                        'category': category_name1
                                    }
                                    result[key].append(info)

                    else:
                        for note in all_notes:
                            if note['category'] == category:
                                if not note['in_reply_to_id']:
                                    if note['category']:
                                        category_name1 = note['category']['name']
                                    info = {
                                        'full_name': note['author']['first_name']+' '+note['author']['last_name'],
                                        'date': note['date'].format('YYYY-MM-DD HH-mm-ss'),
                                        'content': note['content'],
                                        'category': category_name1
                                    }
                                    result[note['id']] = [info]
                        if len(result.keys()) != 0:
                            for key in result.keys():
                                for note in all_notes:
                                    if note['category'] == category and note['in_reply_to_id'] == key:
                                        if note['category']:
                                            category_name1 = note['category']['name']
                                        info = {
                                            'full_name': note['author']['first_name']+' '+note['author']['last_name'],
                                            'date': note['date'].format('YYYY-MM-DD HH-mm-ss'),
                                            'content': note['content'],
                                            'category': category_name1,
                                        }
                                        result[key].append(info)
            if len(result.keys()) != 0:
                file_name = "/tmp/notes-downloading_" + entity['name'] + '_' + category_name + '_' + arrow.now().\
                    format('YYYY-MM-DD HH-mm-ss') + ".csv"
                data = open(file_name, "wb+")
                # there will be one blank line between two different notes
                try:
                    f = csv.writer(data)
                    f.writerow(["name", "time", "content", "category"])
                    for key, item in result.items():
                        for sub in item:
                            f.writerow([
                                sub['full_name'],
                                sub['date'],
                                sub['content'],
                                sub['category']
                                ]
                            )
                        f.writerow('')
                    data.close()
                except Exception:
                    logging.error("Error occurs when making csv file")
                    raise

                _from = 'ftrack@wetaworkshop.co.nz'
                _to = user['email']
                subject = 'notes download'
                text = 'Please check your attachment for notes'
                server = 'utility01.forge.wetaworkshop.co.nz:25'
                file_type = 'csv'
                try:
                    self.send_mail(_from, _to, subject, text, file_name, file_type, server)
                except smtplib.SMTPServerDisconnected:
                    logging.error("server unexpectedly disconnects or an attempt is made to use"
                                  " the SMTP instance before connecting it to a server.")
                    raise
                except smtplib.SMTPResponseException:
                    logging.error("SMTP server returns an error code.")
                    raise
                except smtplib.SMTPSenderRefused:
                    logging.error("Sender address refused.")
                    raise
                except smtplib.SMTPRecipientsRefused:
                    logging.error("All recipient addresses refused.")
                    raise
                except smtplib.SMTPConnectError:
                    logging.error("Error occurred during establishment of a connection with the server.")
                    raise
                except smtplib.SMTPHeloError:
                    logging.error("The server refused our HELO message.")
                    raise
                except smtplib.SMTPAuthenticationError:
                    logging.error("SMTP authentication went wrong. "
                                  "Most probably the server didn’t accept the username/password combination provided.")
                    raise
                try:
                    os.remove(file_name)
                except Exception:
                    logging.error("file cannot be removed")
                    raise

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
        only one entity is selected.

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
            category_id = data['values'].get('note_category')
            self.download_notes(entities, category_id, event['source'])

        return {
            'success': True,
            'message': 'Started downloading notes'
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
            options.insert(0, {'label': 'All', 'value': 'all'})
            return [
                {
                    'value': '## Please select one category ##',
                    'type': 'label'
                }, {
                    'label': 'Note category',
                    'type': 'enumerator',
                    'name': 'note_category',
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

    action_handler = DownloadNoteOnSingleEntityAction(session)
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