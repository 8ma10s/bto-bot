import random
from collections import OrderedDict

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import error
import os

class DriveStorage:

    def __init__(self,root, onHeroku):

        # variables
        self.drive = self.__setupDrive(onHeroku)
        self.dirIndex = {'root':{'id':root, 'entries':self.__makeEntries(root) }}
        self.dataCache = OrderedDict()
        self.cacheSize = 0


    # upload the file to the specific location
    def upload(self, data, location, filename):

        # find (if not, create) the directory the file is supposed to be uploaded.
        curDir = self.__getDirectory(location, self.dirIndex['root'], create=True)

        # prepare to update / upload the file
        if filename in curDir['entries']:
            gFile = self.drive.CreateFile(
                {'title':filename, 
                'id': curDir['entries'][filename]['id'],
                'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
                })
        else:
            gFile = self.drive.CreateFile(
                {'title':filename,
                'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
                })
        
        # upload
        gFile.content = data
        gFile.Upload()
        print('Filename "' + filename + '" uploaded to Drive')
        
        #maintenance
        self.__addToCache(gFile)
        curDir['entries'][filename] = {'id': gFile['id'], 'entries':None}
        return data



            
        """ for dir in targetPath:
            if dir in curDir['entries']:
                if not curDir['entries'][dir]['isDir']:
                    raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                curDir = curDir['entries'][dir]
            else:
                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['entries']:
                    if not curDir['entries'][dir]['isDir']:
                        raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                    curDir = curDir['entries'][dir]
                else:
                    # create new folder
                    newFolder = self.drive.CreateFile(
                        {'title':dir,
                        'parents':[{'id': curDir['id']}],
                        "mimeType": "application/vnd.google-apps.folder"
                        })
                    newFolder.Upload()
                    curDir['entries'][dir] = {'isDir': True, 'id': newFolder['id'], 'entries': {}}
                    curDir = curDir['entries'][dir]
        
        
        self.__refreshDir(curDir['id'], curDir)
        # update file
        if filename in curDir['entries']:
            gFile = self.drive.CreateFile(
                {'title':filename, 
                'id': curDir['entries'][filename]['id'],
                'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
                })
            
        else:
            gFile = self.drive.CreateFile(
                {'title':filename,
                'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
                })


        gFile.content = data
        gFile.Upload()
        self.__reduceCache()
        if gFile['id'] in self.dataCache:
            self.cacheSize -= self.dataCache[gFile['id']].getbuffer().nbytes
            self.dataCache[gFile['id']].close()
        self.dataCache[gFile['id']] = data
        self.cacheSize += data.getbuffer().nbytes
        self.__listFiles.cache_clear()
        curDir['entries'][filename] = {'id': gFile['id'], 'isDir':False, 'entries':{}}
        return data"""

    def download(self, location, filenames=[], exact=False):
        if exact and len(filenames) != 1:
            raise error.InvalidParametersError('if exact=True, there must only be 1 filename argument')
    
        curDir = self.__getDirectory(location, self.dirIndex['root'])

        name = None
        id = None
        # if specified, get specified file
        if not filenames:
            files = [(entryname, entry['id']) for entryname, entry in curDir['entries'].items() if entry['entries'] == None]
            name, id = random.choice(files)
        # if file not specified, choose a random file
        else:
            for entryname, entry in curDir['entries'].items():
                if (exact and  entry['entries'] == None and os.path.splitext(entryname)[0] == os.path.splitext(filenames[0])[0]) \
                or (not exact and entry['entries'] == None and all(filename in entryname for filename in filenames)):
                    name = entryname
                    id = entry['id']
                    break

        # if no file is found, throw an error
        if name == None or id == None:
            raise error.FileNotFoundError('A file with name ' + str(filenames) + ' is not found in "' + os.path.join(*location) + '".')


        # if file is cached, load from cache. If not, download and add to cache
        if id in self.dataCache:
            self.dataCache.move_to_end(id)
            print('File "' + name + '" loaded from cache')
        else:
            gFile = self.drive.CreateFile({'id': id})
            gFile.FetchContent()
            print('File "' + name + '" downloaded from Google Drive')
            self.__addToCache(gFile)

        self.dataCache[id].seek(0)
        return (name, self.dataCache[id])

        """targetPath = location
        curDir = self.dirIndex['root']
        for dir in targetPath:
            if dir in curDir['entries']:
                if not curDir['entries'][dir]['isDir']:
                    raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                curDir = curDir['entries'][dir]
            else:

                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['entries']:
                    if not curDir['entries'][dir]['isDir']:
                        raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                    curDir = curDir['entries'][dir]
                else:
                    raise error.DirectoryNotFoundError('The specified directory: "' +  dir + '" was not found')

        # if cached, no need to connect to Google
        if filenames: 
            for key in list(curDir['entries'].keys()):
                matchObj = curDir['entries'][key]
                if all(filename in key for filename in filenames) and not matchObj['isDir'] and matchObj['id'] in self.dataCache:
                    self.dataCache.move_to_end(matchObj['id'])
                    print('cached, no list load')
                    return (key, self.dataCache[matchObj['id']])

        gFiles = self.drive.ListFile({'q': "'" + curDir['id'] + "' in parents and trashed=false"}).GetList()
        gFiles = list(filter(lambda x: all(y in x['title'] for y in filenames), gFiles))

        if not gFiles:
            raise error.FileNotFoundError('Could not find a file that matches all queries')
        # choose exact match if exists. If not, choose a random file among the ones that matched the query
        gFile = None
        if len(filenames) == 1:
            for match in gFiles:
                print(match['title'])
                if os.path.splitext(match['title'])[0] == os.path.splitext(filenames[0])[0]:
                    gFile = match
        if not gFile:
            gFile = random.choice(gFiles)
        
        # if cached, return cache
        if gFile['id'] in self.dataCache:
            self.dataCache.move_to_end(gFile['id'])
            print('cached, list load')
            return (gFile['title'], self.dataCache[gFile['id']])
        else:
            gFile.FetchContent()
            self.__reduceCache()
            self.dataCache[gFile['id']] = gFile.content
            self.cacheSize += gFile.content.getbuffer().nbytes

            curDir['entries'][gFile['title']] = {'id': gFile['id'], 'isDir':False, 'entries':{}}
            print('not cached')
            return (gFile['title'], gFile.content) """
    

    def listFiles(self, location, filenames=[]):
        curDir = self.__getDirectory(location, self.dirIndex['root'])
        return [name for name in curDir['entries'] if all(filename in name for filename in filenames)]

    """
    @lru_cache()
    def __listFiles(self, location):
        targetPath = list(location)
        curDir = self.dirIndex['root']
        for dir in targetPath:
            if dir in curDir['entries']:
                if not curDir['entries'][dir]['isDir']:
                    raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                curDir = curDir['entries'][dir]
            else:

                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['entries']:
                    if not curDir['entries'][dir]['isDir']:
                        raise error.NotADirectoryError('name: "' + dir + '" is not a directory')
                    curDir = curDir['entries'][dir]
                else:
                    raise error.DirectoryNotFoundError('The specified directory: "' +  dir + '" was not found')
        
        print("'" + curDir['id'] + "' in parents and trashed=false")
        gFiles = self.drive.ListFile({'q': "'" + curDir['id'] + "' in parents and trashed=false"}).GetList()
        return [gFile['title'] for gFile in gFiles]
        




    
    def __refreshDir(self, id, curDir):
        ## make a dictionary of subdirectories, with key being the title, and values being dict of id, isDir, and empty subDir
        ## then set it equal to current folder's subdirectory
        curDir['entries'] = { result['title']:{'id':result['id'], 
        'isDir':(True if result['mimeType'] == 'application/vnd.google-apps.folder' else False), 
        'entries': {} if result['title'] not in curDir['entries'] else curDir['entries'][result['title']]['entries']} 
        for result in self.drive.ListFile({'q': "'" + id + "' in parents and trashed=false"}).GetList() } """

    def __reduceCache(self):
        if self.cacheSize > 262144000:
            print('Reducing cache for DriveStorage')
            for _ in range(50):
                bio = self.dataCache.pop(last = False)
                self.cacheSize -= bio.getbuffer.nbytes
                bio.close()
        else:
            return

    def __addToCache(self, gFile):
        if gFile['id'] in self.dataCache:
            self.cacheSize -= self.dataCache[gFile['id']].getbuffer().nbytes
            self.dataCache[gFile['id']].close()
            print('Filename "' + gFile['title'] + '" deleted in cache')

        self.dataCache[gFile['id']] = gFile.content
        self.cacheSize += gFile.content.getbuffer().nbytes
        self.__reduceCache()
        print('Filename "' + gFile['title'] + '" added in cache')

    def __getDirectory(self, targetPath, curDir, create=False):
        """Traverse and get the content (entries) of the specified directory.
        If a directory within a path is nonexistent, it creates that directory (if create=True), or throw and error if False."""
        if targetPath == []:
            return curDir

        dir = targetPath[0]
        if dir not in curDir['entries']:
            if create:
                newFolder = self.drive.CreateFile(
                    {'title':dir,
                    'parents':[{'id': curDir['id']}],
                    "mimeType": "application/vnd.google-apps.folder"
                    })
                newFolder.Upload()
                curDir['entries'][dir] = {'id': newFolder['id'], 'entries': {}}
                return self.__getDirectory(targetPath[1:], curDir['entries'][dir], create=create)
            else:
                raise error.DirectoryNotFoundError('The directory called "' + targetPath[0] + '" was not found.')
        else:
            if curDir['entries'][dir]['entries'] == None:
                raise error.NotADirectoryError('An entry named "' + dir + '" is not a directory.')
            else:
                return self.__getDirectory(targetPath[1:], curDir['entries'][dir], create=create)


    def __makeEntries(self, id):
        """A recursive function that retrieves the structure of every files/directories under a directory with id, and returns a dict
        representing that structure."""
        results = self.drive.ListFile({'q': "'" + id + "' in parents and trashed=false"}).GetList()
        print([result['title'] for result in results])
        return { result['title']:{'id':result['id'], 
        'entries': self.__makeEntries(result['id']) if result['mimeType'] == 'application/vnd.google-apps.folder' else None} 
        for result in results if not result['title'].startswith('.')}

    def __setupDrive(self, onHeroku):
        gauth = GoogleAuth()
        if onHeroku:
            from oauth2client.client import Credentials
            import os
            import oauth2client.clientsecrets as clientsecrets
            # load credentials from env
            gauth.credentials = Credentials.new_from_json(os.environ.get('MYCREDS'))
            # set client_config from env, and change backend to settings to tell it to load from settings in the future
            _, client_info = clientsecrets.loads(os.environ.get('CLIENT_SECRETS'))
            client_info['revoke_uri'] = client_info.get('revoke_uri')
            client_info['redirect_uri'] = client_info['redirect_uris'][0]
            gauth.settings['client_config_backend'] = 'settings'
            gauth.settings['client_config'] = client_info
        else:
            gauth.LoadCredentialsFile('mycreds.json') # replace with loadEnv if heroku
        if gauth.credentials is None:
            # Authenticate if they're not there
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            # Refresh them if expired
            gauth.Refresh()
        else:
            # Initialize the saved creds
            gauth.Authorize()
        # Save the current credentials to a file
        if onHeroku:
            os.environ['MYCREDS'] = Credentials.to_json(gauth.credentials)
        else:
            gauth.SaveCredentialsFile('mycreds.json') # replace with saveToEnv if heroku

        return GoogleDrive(gauth)
    
