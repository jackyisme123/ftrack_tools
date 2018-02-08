from Tkinter import *

import ftrack_api
import tkMessageBox
import collections
import cPickle as pickle
import threading

# ftrack configuration
SERVER_URL = 'http://192.168.9.82/'
API_KEY = '72baaed0-1816-11e7-8c7e-005056a84326'
API_USER = 'root'
AUTO_SAVE_TIME = 10

class quick_notes_gui:
    '''GUI for quick notes'''
    task_frame_count = 0
    submit_info = {}
    save_message = collections.OrderedDict()
    project = None
    user = None
    search_labelframe = None

    def __init__(self, app, session):
        '''set GUI'''
        #destroy previous GUI first
        for widget in app.winfo_children():
            widget.destroy()
        app.title("Quick notes")
        app.geometry('1024x800')
        canvas = Canvas(app, borderwidth=0)
        frame = Frame(canvas)
        vsb = Scrollbar(app, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((4,4), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda event, canvas=canvas: onFrameConfigure(canvas))
        menu = Menu(app)
        app.config(menu=menu)
        fileMenu = Menu(menu)
        menu.add_cascade(label='File', menu=fileMenu)
        fileMenu.add_command(label='New', command=lambda (app, session) =(app, session):self.new_project((app, session)))
        fileMenu.add_command(label='Save', command= self.save_project)
        fileMenu.add_command(label='Load', command = self.load_project)
        fileMenu.add_separator()
        fileMenu.add_command(label='Quit', command=lambda app=app:self.quit(app))
        self.session = session
        frame1 = Frame(frame)
        frame1.pack(side=TOP, fill=X, pady=20)
        self.choose_project_label = Label(frame1, text='Enter project name:')
        self.choose_project_entry = Entry(frame1)
        self.choose_user_label = Label(frame1, text='Enter user name:')
        self.choose_user_entry = Entry(frame1)
        self.choose_project_button = Button(frame1, text='Search', command=self.search_project)
        self.choose_project_err_msg = Label(frame1, text='Cannot find that project, please check your project name', fg='red')
        self.choose_project_label.grid(row=0, column=0, padx=10)
        self.choose_project_entry.grid(row=0, column=1, padx=10)
        self.choose_user_label.grid(row=0, column=2, padx=10)
        self.choose_user_entry.grid(row=0, column=3, padx=10)
        self.choose_project_button.grid(row=0, column=4, padx=10)
        self.submit_button = Button(frame1, text='submit', bg='green', command=self.submit)
        self.frame2 = Frame(frame)
        self.search_task_label = Label(self.frame2, text='Enter task name:')
        self.search_task_entry = Entry(self.frame2)
        self.search_task_button = Button(self.frame2, text='Search', command=self.search_task)
        self.search_task_label.grid(row=0, column=0, padx=10)
        self.search_task_entry.grid(row=0, column=1, padx=10)
        self.search_task_button.grid(row=0, column=2, padx=10)
        self.search_labelframe = LabelFrame(self.frame2, text="Search Result ---- Click to add task")
        self.frame3 = Frame(frame)
        self.tasks = []



    def search_project(self):
        '''search project by name'''
        self.choose_project_err_msg.grid_remove()
        project_name = self.choose_project_entry.get()
        user_name = self.choose_user_entry.get()
        try:
            self.project = get_project(self.session, project_name)
        except Exception:
            self.choose_project_err_msg.grid(row=0, column=5, padx=10)
            return
        try:
            self.user = get_user(self.session, user_name)
        except Exception:
            self.choose_project_err_msg['text'] = 'Cannot find that user, please check your user name'
            self.choose_project_err_msg.grid(row=0, column=5, padx=10)
            return

        self.pack_frame1()
        self.tasks = get_tasks_from_project(self.project)
        self.pack_frame2()

    def pack_frame1(self):
        '''show frame1 in window'''
        self.choose_project_label['text'] = "Project: "+self.project['full_name'] +"                               User: "+self.user['first_name']+ " "+self.user['last_name']
        self.choose_project_entry.grid_remove()
        self.choose_user_entry.grid_remove()
        self.choose_user_label.grid_remove()
        self.choose_project_button.grid_remove()
        # when project and user are confirmed, auto save program starts
        k = ThreadJob(self.save, event, AUTO_SAVE_TIME)
        if self.project and self.user:
            k.start()

    def pack_frame2(self):
        '''show frame2 in window'''
        self.frame2.pack(side=TOP, fill=X, pady=10, padx=15)

    def search_task(self):
        '''search tasks by key word'''
        for widget in self.search_labelframe.winfo_children():
            widget.destroy()
        self.search_labelframe.grid(row=1, column=0, columnspan=3, sticky=W)
        task_name = self.search_task_entry.get()
        row = 0
        col = 0
        for task in self.tasks:
            if task_name.lower() in task['name'].lower():
                task_button = Button(self.search_labelframe, text=task['name'])
                task_button.bind("<ButtonPress-1>", lambda event: self.use_task(event))
                task_button.grid(row=row, column=col, padx=10, pady=10)
                col += 1
                if col == 3:
                    col = 0
                    row += 1

    def use_task(self, event):
        '''add tasks by click task name button'''
        self.submit_button.grid(row=0, column=4, sticky=E, padx=50)
        task_frame = Frame(self.frame3)
        task_name = event.widget.cget("text")
        if task_name in self.save_message.keys():
            tkMessageBox.showinfo("Warning", "Task has already existed")
        else:
            task_name_label = Label(task_frame, text=task_name, width=50)
            task_delete_button = Button(task_frame, text='Delete')
            task_delete_button.bind("<ButtonPress-1>", lambda event: self.delete_task(event))
            task_note_text = Text(task_frame, height=5, width=100)
            task_note_text.bind("<Leave>", lambda event, task_name= task_name: self.focusOut(event, task_name))
            task_delete_button.grid(row=0, column=1, padx=10)
            task_name_label.grid(row=0, column=0)
            task_note_text.grid(row=1, column=0, columnspan=2, pady=5)
            task_frame.pack(side=BOTTOM, fill=X, pady=5)
            self.frame3.pack(side=TOP, fill=BOTH, pady=10, padx=15)
            self.save_message[task_name]=''
            self.task_frame_count += 1

    def delete_task(self, event):
        '''delete task by click button'''
        parent = event.widget.winfo_parent()
        parent_widget = event.widget._nametowidget(parent)
        for child_widget in parent_widget.children.values():
            if str(child_widget.__class__) == 'Tkinter.Label':
                task_name = child_widget['text']
                break
        parent_widget.destroy()
        del self.save_message[task_name]
        self.task_frame_count -= 1
        if(self.task_frame_count == 0):
            self.submit_button.grid_forget()

    def submit(self):
        '''submit function'''
        task_frames = self.frame3.winfo_children()
        for task_frame in task_frames:
            submit_note = task_frame.winfo_children()[2].get("1.0",'end-1c')
            self.submit_info[task_frame.winfo_children()[0]['text']] = submit_note.replace("\n", "<br>")
        submit_info_to_ftrack(self.submit_info, self.session, self.user, self.project)
        for child in self.frame3.winfo_children():
            child.destroy()

    def quit(self, app):
        '''quit GUI'''
        app.destroy()


    def new_project(self, arg):
        '''create new project'''
        app, session = arg
        quick_notes_gui(app, session)

    def save(self):
        '''save data in project'''
        if self.choose_project_label['text'] == 'Enter project name:':
            return 0
        else:
            project_id = self.project['id']
            user_id = self.user['id']
            with open('save.p', 'wb') as f:
                pickle.dump({
                    "project_id": project_id,
                    "user_id": user_id,
                    "notes": self.save_message
                }, f)
            return 1

    def save_project(self):
        '''save project reflect result with pop-up window'''
        if(self.save()):
            tkMessageBox.showinfo("Successful", "Saving successfully")
        else:
            tkMessageBox.showinfo("Warning", "Nothing for saving!")

    def load_project(self):
        '''load project'''
        try:
            with open('save.p', 'rb') as f:
                save_info = pickle.load(f)
        except Exception:
            tkMessageBox.showinfo("Failure", "Loading failure!")
        project_id = save_info['project_id']
        user_id = save_info['user_id']
        notes_msg = save_info['notes']
        self.project = self.session.query("Project where id is {0}".format(project_id)).one()
        self.user = self.session.query("User where id is {0}".format(user_id)).one()
        self.tasks = get_tasks_from_project(self.project)
        self.save_message = notes_msg
        self.search_labelframe.grid_remove()
        if len(notes_msg) == 0:
            self.pack_frame1()
            self.pack_frame2()
            for widget in self.frame3.winfo_children():
                widget.destroy()
            self.submit_button.grid_forget()
            self.task_frame_count = 0
        else:
            self.pack_frame1()
            self.submit_button.grid(row=0, column=4, sticky=E, padx=50)
            self.pack_frame2()
            for key,value in notes_msg.items():
                task_name = key
                note_content = value
                task_frame = Frame(self.frame3)
                task_name_label = Label(task_frame, text=task_name, width=50)
                task_delete_button = Button(task_frame, text='Delete')
                task_delete_button.bind("<ButtonPress-1>", lambda event: self.delete_task(event))
                task_note_text = Text(task_frame, height=5, width=100)
                task_note_text.insert(END, note_content)
                task_note_text.bind("<Leave>", lambda event, task_name= task_name: self.focusOut(event, task_name))
                task_delete_button.grid(row=0, column=1, padx=10)
                task_name_label.grid(row=0, column=0)
                task_note_text.grid(row=1, column=0, columnspan=2, pady=5)
                task_frame.pack(side=BOTTOM, fill=X, pady=5)
                self.frame3.pack(side=TOP, fill=BOTH, pady=10, padx=15)
                self.task_frame_count = len(notes_msg)

    def focusOut(self, event, task_name):
        '''save result when mouse move out of text area'''
        note_content = event.widget.get("1.0", 'end-1c')
        self.save_message[task_name] = note_content


def get_tasks_from_project(project):
    '''pick tasks and milestones up from project'''
    descendants = project['descendants']
    result = []
    for desc in descendants:
        if(desc['object_type']['name']=='Task'):
            result.append(desc)
    return result

def get_session():
    '''get session from ftrack'''
    return ftrack_api.Session(
        server_url=SERVER_URL,
        api_key=API_KEY,
        api_user=API_USER
    )

def get_project(session, project_name):
    '''get project by name'''
    return session.query("Project where full_name is '{0}'".format(project_name)).one()

def get_user(session, user_name):
    '''get user by name'''
    return session.query("User where username is '{0}'".format(user_name)).one()

def onFrameConfigure(canvas):
    '''Reset the scroll region to encompass the inner frame'''
    canvas.configure(scrollregion=canvas.bbox("all"))

def submit_info_to_ftrack(info, session, user, project):
    catagory = session.query("NoteCategory where name is 'Client feedback'").one()
    for key, value in info.items():
        task_name = key
        note_content = value
        task = session.query("Task where name is '{0}' and project.name is '{1}'".format(task_name, project['full_name'])).first()
        # empty note won't be submitted
        if value != '':
            task.create_note(note_content, user, category=catagory)
    try:
        session.commit()
        tkMessageBox.showinfo("Successful", "Successful submission!")
    except Exception:
        tkMessageBox.showinfo("Failure", "Sorry, your notes are not submitted!")
        session.rollback()
        raise

class ThreadJob(threading.Thread):
    '''for auto save job'''
    def __init__(self,callback,event,interval):
        '''runs the callback function after interval seconds

        :param callback:  callback function to invoke
        :param event: external event for controlling the update operation
        :param interval: time in seconds after which are required to fire the callback
        :type callback: function
        :type interval: int
        '''
        self.callback = callback
        self.event = event
        self.interval = interval
        super(ThreadJob,self).__init__()

    def run(self):
        while not self.event.wait(self.interval):
            self.callback()



event = threading.Event()

def main():
    session = get_session()
    app = Tk()
    quick_notes_gui(app, session)
    app.mainloop()

if __name__ == "__main__":
    main()