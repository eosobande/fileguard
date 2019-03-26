import webapp2
import jinja2
from google.appengine.api import users
from google.appengine.ext import ndb, blobstore
from models import *
from handlers import *
import os

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)

class MainPage(webapp2.RequestHandler):

    def __init__(self, request, response):

        self.initialize(request, response)
        user = users.get_current_user()

        if user:
            url = users.create_logout_url(self.request.uri)
            url_string = 'logout'
            
            self.myuser = MyUser.get(user.user_id())           
            if not self.myuser:
                self.myuser = MyUser(id=user.user_id(), email=user.email())
                self.myuser.put()                
                
            self.root = Directory.get_dir(self.myuser.key)
            if not self.root:
                self.root = Directory(id=self.myuser.key.id()+'/', name='/', parent=self.myuser.key)                
                self.root.put()

        else:
            url = users.create_login_url(self.request.uri)
            url_string = 'login'

        self.template_values = {
            'url' : url,
            'url_string' : url_string,
            'user' : user
        }

    def template(self, cwd_id='', directory=None, template='main.html', shared_parent=None):
        
        if directory:
            
            directory.folders.sort()
            path = []
            parent = directory
            while parent and (parent.is_users_dir(self.myuser.key) or parent.is_shared_to_me(self.myuser.key)) or shared_parent:
                
                url = parent.key.id()
                if parent.is_users_dir(self.myuser.key):
                    url = url.replace(self.myuser.key.id(), '')
                
                path.append({'name': parent.name, 'url':url})
                
                if parent == shared_parent:
                    break
                             
                parent = parent.get_parent()
                
            if not directory.is_users_dir(self.myuser.key):
                path.append({'name':'/', 'url':''})
                
            path.reverse()
            
            all_dirs = None
            if not shared_parent:
                all_dirs = self.root.get_all_sub_folders(True)
            elif shared_parent and self.template_values['writable']:
                all_dirs = shared_parent.get_all_sub_folders(True)
                
            self.template_values.update({
                'cwd': directory,
                'files': sorted(directory.files, key=lambda x: x.name),
                'upload_url': blobstore.create_upload_url('/upload'),
                'cur_dir': '/'+cwd_id,
                'path': path,
                'all_dirs': all_dirs
            })
           
        self.response.headers['Content-Type'] = 'text/html'
        template = JINJA_ENVIRONMENT.get_template(template)
        self.response.write(template.render(self.template_values))

    def get(self, cwd_id=""):
 
        if self.template_values['user']:
 
            directory = Directory.get_dir(self.myuser.key, cwd_id) 
            if not directory or not directory.is_users_dir(self.myuser.key):
                self.redirect('/dir/')   
            else:
                self.template(cwd_id, directory)
                
        elif cwd_id:
            self.redirect('/')             
        else:
            self.template()
         

    def delete_selected_items(self, ancestor):
        
        folders = self.request.get_all('folders')
        files = self.request.get_all('files')
        
        for folder in folders:
            folder = ancestor.get_child(folder)
            if folder:
                folder.remove()
        
        if len(files) > 0:
            files = map(int, files)
            files.sort(reverse=True)
            for f in files:
                del ancestor.files[int(f)]
            
            ancestor.put()

    def create_new_directory(self, ancestor, name, parent):
        key_name = ancestor.key.id() + name + '/'
        directory = Directory(id=key_name, name=name, parent=parent)
        if ancestor.folder_exists(name):
            return "A directory with the same name already exists"
        else:
            directory.put()
            ancestor.folders.append(name)
            ancestor.put()


    def move_selected_items(self, ancestor, user_key):
        destination = self.request.get('destination').strip()
        folders = self.request.get_all('folders')
        files = self.request.get_all('files')
        if not destination:
            return 'Please select a destination folder'
        elif not (len(folders) > 0 or len(files) > 0):
            return 'No file(s) and/or folder(s) selected'
        else:
            destination = Directory.get_by_id(user_key.id() + destination, user_key)
            if not destination or not destination.is_users_dir(user_key):
                return 'Invalid destination folder'
            elif destination == ancestor:
                return 'Cannot move into the same directory'
            else:
                ancestor.move_folders(folders, destination)
                ancestor.move_files(files, destination)

    def post(self, cwd_id=''):
 
        if not self.template_values['user']:
 
            self.redirect('/')
            
        else:
 
            ancestor = Directory.get_dir(self.myuser.key, cwd_id)
            button = self.request.get('button')
            error = ''

            if button == 'Create':
                name = self.request.get('name').strip()                
                if name and ancestor and ancestor.is_users_dir(self.myuser.key):
                                                                                                    
                    error = self.create_new_directory(ancestor, name, self.myuser.key)
                    if not error:    
                        self.redirect('/dir/' + cwd_id)              
     
                else:
                    error = "Oops! Something went wrong."
                
                if error:
                    self.template_values['error'] = error
                    self.template(cwd_id, ancestor)
                                                                                                    
                    key_name = ancestor.key.id() + name + '/'
                    directory = Directory(id=key_name, name=name, parent=ancestor.key.parent())
                     
                    if ancestor.folder_exists(name):
                        error = "A directory with the same name already exists"
                    else:
                        directory.put()
                        ancestor.folders.append(name)
                        ancestor.put()
                        self.redirect(self.request.referer)                    
     
                else:
                    error = "Please type in a valid folder name"
                
                if error:
                    self.template_values['error'] = error
                    self.template(cwd_id, ancestor)
                    
            elif button == 'Delete Selected Items':
                
                self.delete_selected_items(ancestor)                    
                self.redirect(self.request.referer)        

            elif button == 'Move Selected Items':
                error = self.move_selected_items(ancestor, self.myuser.key)                        
                if error:
                    self.template_values['error'] = error
                    self.template(cwd_id, ancestor)
                else:
                    self.redirect(self.request.referer)    
                
            else:
                self.redirect(self.request.referer)  
        
                
class SharedHandler(MainPage):
    
    def get(self, cwd_id=""):
 
        if self.template_values['user']:
            
            if not cwd_id:
            
                shared_folders = []                
                for share in Share.ancestor_query().filter(Share.user == self.myuser.key).fetch():                    
                    shared_folders.append(Directory.get_by_id(share.folder.id(), share.folder.parent())) 
                                    
                self.template_values['shared_folders'] = shared_folders
                self.template(template='shared.html')
                    
            else:
                myuser, directory, parent = check(self.myuser.key, cwd_id)
                if myuser and directory:
                     
                    locks = []                                
                    for child in directory.folders:
                        child = directory.get_child(child)
                        locks.append(self.myuser.key in child.lock)
                                  
                    self.template_values.update({
                        'writable': has_write_permission(self.myuser.key, parent),
                        'locks': locks,
                        'owner': myuser.email
                    })                             
                    self.template(cwd_id, directory, 'shared_main.html', parent)

                else:
                    self.redirect('/shared/')
         
        else:
            self.template()
         
    def post(self, cwd_id=''):  
               
        myuser, ancestor, parent = check(self.myuser.key, cwd_id)
        button = self.request.get('button')    
                  
        if myuser and ancestor and has_write_permission(self.myuser.key, parent):
                         
            if button == 'Delete Selected Items':
                
                self.delete_selected_items(ancestor)                   
                self.redirect(self.request.referer)            

            elif button == 'Create':
                error = ''
                name = self.request.get('name').strip()
                if name:                    
                    error = self.create_new_directory(ancestor, name, myuser.key)
                    if not error:
                        self.redirect(self.request.referer)                    
     
                else:
                    error = "Please type in a valid folder name"
                
                if error:
                    self.template_values.update({
                        'error': error,
                        'owner': myuser.email,
                        'writable': True
                    })
                    self.template(cwd_id, ancestor, 'shared_main.html')

            elif button == 'Move Selected Items':
                error = self.move_selected_items(ancestor, myuser.key)                        
                if error:
                    self.template_values['error'] = error
                    self.template(cwd_id, ancestor, 'shared_main.html')
                else:
                    self.redirect(self.request.referer) 

class PropertiesHandler(MainPage):
    
    def get(self, cwd_id=""):
 
        if self.template_values['user']:
 
            directory = Directory.get_dir(self.myuser.key, cwd_id)
            
            if not directory or not directory.is_users_dir(self.myuser.key):
                self.redirect('/dir/')   
            else:
            
                self.template_values.update({
                    'cwd': directory,
                    'guests': directory.get_guests(),
                    'cur_dir': cwd_id
                })
                
                self.template(cwd_id, template='properties.html')
                   
        elif cwd_id:
            self.redirect('/')             
        else:
            self.template(template='properties.html')
            
         
    def post(self, cwd_id=''):
 
        if not self.template_values['user']:
 
            self.redirect('/')
            
        else:
 
            ancestor = Directory.get_dir(self.myuser.key, cwd_id)
            button = self.request.get('button')
            error = ''
                    
            if button == 'Share':
                 
                permission = self.request.get('permission').strip()
                email = self.request.get('email').strip()
                
                if not email:
                    error = 'Please enter a valid email address'
                elif email == self.myuser.email:
                    error = 'You own this folder, you cannot share it to yourself'
                elif permission not in ['r','rw']:
                    error = 'Please select a valid permission'
                else:          
                    guest = MyUser.query(MyUser.email == email).get()
                    if guest:
                        if Share.ancestor_query().filter(Share.user == guest.key, Share.folder == ancestor.key).count() == 0:
                            Share(
                                parent=ndb.Key(Share, 'Share'),
                                folder=ancestor.key,
                                user=guest.key,
                                permission=permission
                            ).put()
                            ancestor.undo_inner_share()                            
                            self.redirect(self.request.referer)
                        else:
                            error = "Folder is already shared with " + email
                    else:
                        error = 'User ' + email + ' does not exist'
                
                self.template_values.update({
                    'cwd': ancestor,
                    'guests': ancestor.get_guests(),
                    'cur_dir': cwd_id,
                    'error': error
                })
                self.template(cwd_id, template='properties.html')
                
            elif button == 'Unshare' or button == 'Unlock':
                ancestor.unshare(self.request.get_all('guests'), self.myuser.email)
                self.redirect(self.request.referer)   
            
            else:
                self.redirect(self.request.referer)

    
app = webapp2.WSGIApplication([
    ('/', MainPage),         
    (r'/dir/(.*)', MainPage),
    (r'/shared/(.*)', SharedHandler),
    (r'/properties/(.*)', PropertiesHandler),
    ('/upload', UploadHandler),
    (r'/download/(.*)', DownloadHandler)
], debug = True)
