from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from models import MyUser, File
from funcs import check, has_write_permission

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    
    def post(self):
        
        user = users.get_current_user()
        if user == None:
            self.redirect('/')
        else:
        
            current_user = MyUser.get(user.user_id())
            
            dir_id = self.request.get('dir')
            
            owner_user, directory, parent = check(current_user.key, dir_id)
                           
            if owner_user and directory and (directory.is_users_dir(current_user.key) or has_write_permission(current_user.key, parent)):
            
                for upload in self.get_uploads():
                    
                    blobinfo = blobstore.BlobInfo(upload.key())
                    
                    my_file = File(name=blobinfo.filename, blob=upload.key())
                    
                    if not directory.file_exists(my_file.name):            
                        directory.files.append(my_file)
                        
                directory.put()
            
                self.redirect(self.request.referer)
        
class DownloadHandler(blobstore_handlers.BlobstoreDownloadHandler):
    
    def get(self, abs_path):
        
        user = users.get_current_user()
        if user == None:
            self.redirect('/')
        else:
        
            current_user = MyUser.get(user.user_id())
            
            abs_path = abs_path.split('/')
            
            file_index = abs_path[len(abs_path) - 1 if len(abs_path) > 2 else 1]
                
            abs_path[len(abs_path) - 1] = ''
            abs_path = '/'.join(abs_path)
            
            owner_user, directory, parent = check(current_user.key, abs_path)
            
            if file_index and owner_user and directory:
                my_file = directory.files[int(file_index)]
                self.send_blob(my_file.blob, save_as=my_file.name)
            else:
                self.redirect('/')
                
        
