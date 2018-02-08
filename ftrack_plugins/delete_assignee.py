import ftrack_api

#set project_id and assignee name wants to delete
project_id = "4b22068a-e926-11e6-b3b2-005056a84326"
assignee = 'chris.williamson'


session = ftrack_api.Session(
    server_url='http://192.168.9.82/',
    api_key='72baaed0-1816-11e7-8c7e-005056a84326',
    api_user='root'
)

project = session.query('Project where id is {0}'.format(project_id)).one()
descendants = project['descendants']
tasks = []
for descendant in descendants:
    if descendant['object_type']['name'] == 'Task':
        tasks.append(descendant)

for task in tasks:
    appointments = session.query('Appointment where resource.username is "{0}" and context_id is "{1}"'.format(assignee, task['id']))
    for appointment in appointments:
        session.delete(appointment)

session.commit()