
from models import MyUser, Directory, Share
        
def check(current_user_key, cwd_id):
    
    owner = MyUser.get(cwd_id.split('/')[0])   
    if owner:
                      
        directory = Directory.get_by_id(cwd_id, owner.key); 
        if directory:
            
            parent = None
            
            is_shared = directory.is_users_dir(current_user_key)
            if not is_shared:
                parent = directory
                                        
                while parent and not is_shared and current_user_key not in parent.lock:
                    is_shared = parent.is_shared_to_me(current_user_key)
                    if not is_shared:
                        parent = parent.get_parent()
                    
            if is_shared:
                return owner, directory, parent
            
    return None, None, None

def has_write_permission(myuser_key, parent):
    query = Share.ancestor_query().filter(Share.user == myuser_key)
    share = query.filter(Share.folder == parent.key).get()
    return share.permission == 'rw'

