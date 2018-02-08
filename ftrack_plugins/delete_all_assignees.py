import ftrack_api

#set project_id and folder name
project_id = "d4d30ed6-78a2-11e7-b18d-005056a84326"
folder_name = "z-Complete"


session = ftrack_api.Session(
    server_url='http://192.168.9.82/',
    api_key='72baaed0-1816-11e7-8c7e-005056a84326',
    api_user='root'
)

project = session.query('Project where id is {0}'.format(project_id)).one()
descendants = project['descendants']
tasks = []
for descendant in descendants:
    if descendant['name'] == folder_name:
        for sub_des in descendant['descendants']:
            if sub_des['object_type']['name'] == 'Task':
                tasks.append(sub_des)

for task in tasks:
    users = session.query('User where assignments any (context_id = "{0}")'.format(task['id']))
    for user in users:
        appointments = session.query('Appointment where resource.username is "{0}" and context_id is "{1}"'.format(user['username'], task['id']))
        for appointment in appointments:
            session.delete(appointment)

session.commit()