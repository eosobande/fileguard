from google.appengine.ext import ndb

class MyUser(ndb.Model):
	email = ndb.StringProperty()
	
	@staticmethod
	def get(user_id):
		return ndb.Key('MyUser', user_id).get()
	
class Share(ndb.Model):
	folder = ndb.KeyProperty()
	permission = ndb.StringProperty()
	user = ndb.KeyProperty()
	
	@staticmethod
	def ancestor_query():
		return Share.query(ancestor=ndb.Key(Share, 'Share'))
	
class File(ndb.Model):
	name = ndb.StringProperty()
	blob = ndb.BlobKeyProperty()

class Directory(ndb.Model):
	name = ndb.StringProperty()
	folders = ndb.StringProperty(repeated=True)
	files = ndb.StructuredProperty(File, repeated=True)
	lock = ndb.KeyProperty(repeated=True)
	created = ndb.DateTimeProperty(auto_now_add=True)
	
	@staticmethod
	def get_dir(myuser_key, cwd_id=''):
		return Directory.get_by_id(myuser_key.id() + '/' + cwd_id, myuser_key)
	
	def get_child(self, name):
		return Directory.get_by_id(self.key.id() + name + '/', self.key.parent())
	
	def remove(self):
		if not self.is_root_dir() and len(self.files) == 0 and len(self.folders) == 0:
			parent = self.get_parent()
			del parent.folders[parent.folders.index(self.name)]
			self.key.delete()				
			parent.put()
	
	def move_folders(self, folders, destination):
		
		for folder in folders:
			if folder not in destination.folders:
				
				child = self.get_child(folder)				
				if not destination.is_sub_folder_of(child):
								
					key_name = destination.key.id() + folder + '/'
					new = Directory(
						id=key_name,
						name=folder,
						folders=child.folders,
						files=child.files,
						lock=child.lock,
						created=child.created,
						parent=self.key.parent()
					)
					new.put()
					
					destination.folders.append(folder)				
					del self.folders[self.folders.index(folder)]					
					for share in Share.ancestor_query().filter(Share.folder == child.key).fetch():						
						share.folder = new.key
						share.put()
					
					child.key.delete()
				
		destination.put()
		self.put()
	
	def move_files(self, indexes, destination):
		
		indexes = map(int, indexes)
		indexes.sort(reverse=True)

		for i in indexes:	
			if not destination.file_exists(self.files[i].name):
				destination.files.append(self.files[i])
				del self.files[i]
				
		destination.put()
		self.put()

	def get_parent(self):		
		return None if self.is_root_dir() else Directory.get_dir(self.key.parent(), self.get_parent_path())

	def get_parent_path(self):			
		path = self.key.id().split('/')
		del path[len(path)-2]
		del path[0]
		return '/'.join(path)

	def folder_exists(self, name):		
		return name in self.folders
	
	def is_root_dir(self):
		return self.name == '/'	
	
	def is_sub_folder_of(self, parent):			
		path = self.abs_path()
		return any(abs_path == path for abs_path in parent.get_all_sub_folders(True))
	
	def is_users_dir(self, myuser_key):		
		return self.key.parent() == myuser_key
	
	def file_exists(self, my_file):
		return any(f.name == my_file for f in self.files)	
	
	def get_guests(self):
		
		guests = []		
		directory = self
		while directory:
			for share in Share.ancestor_query().filter(Share.folder == directory.key).fetch(projection=[Share.user]):
				guests.append(MyUser.get_by_id(share.user.id()))
				
			if directory.is_root_dir():
				break
			else: 
				directory = directory.get_parent()
			
		return guests
	
	def unshare(self, emails, my_email):

		for email in emails:
			if email != my_email:
				user = MyUser.query(MyUser.email == email).get()
				guest = Share.query(Share.folder == self.key).filter(Share.user == user.key).get()
			
				if guest: # delete
					guest.key.delete()
					self.undo_inner_lock(user.key)
					
				elif user.key in self.lock: # unlock
					del self.lock[self.lock.index(user.key)]
					self.put()
					self.undo_inner_lock(user.key)
						
				else: # lock
					self.lock.append(user.key)
					self.put()
	
	def undo_inner_lock(self, user_key):
		
		if user_key and user_key != self.key.parent():
			
			undone = False
			for child in self.folders:
				child = self.get_child(child)
				
				if user_key in child.lock:
					undone = True
					del child.lock[child.lock.index(user_key)]
					child.put()
					
			if not undone:
				for child in self.folders:
					self.get_child(child).undo_inner_lock(user_key)
	
	def undo_inner_share(self):
		for child in self.folders:
			child = self.get_child(child)
			if not ndb.delete_multi(Share.ancestor_query().filter(Share.folder == child.key).fetch(keys_only=True)):
				child.undo_inner_share()			
	
	def get_all_sub_folders(self, inclusive=False):
		
		folders = []		
		if inclusive:
			folders.append(self.abs_path())			
		
		self.folders.sort()
		for child in self.folders:
			child = self.get_child(child)
			folders.append(child.abs_path())
			folders.extend(child.get_all_sub_folders())
			
		return folders
	
	def abs_path(self):
		return self.key.id().replace(self.key.parent().id(), '')
	
	def is_shared_to_me(self, myuser_key):
		return Share.ancestor_query().filter(Share.user == myuser_key).filter(Share.folder == self.key).count() > 0
	
		
		
		
		
		
			
			