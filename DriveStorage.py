import configparser
import random
from functools import lru_cache

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from collections import OrderedDict


class DirectoryNotFoundError(Exception):
    """Exception thrown when a specified directory is not found"""

class FileNotFoundError(Exception):
    """Exception throw when a specified file is not found"""

class IsNotDirectoryError(Exception):
    """Exception thrown when a specified directory is a file"""

class DriveStorage:

    def __init__(self,root):
        gauth = GoogleAuth()
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
        gauth.SaveCredentialsFile('mycreds.json') # replace with saveToEnv if heroku

        # variables
        self.drive = GoogleDrive(gauth)
        self.dirTree = {'root':{'id':root, 'isDir': True, 'subdir':{}}}
        self.dataCache = OrderedDict()
        self.cacheSize = 0


    # upload the file to the specific location
    def upload(self, data, location, filename):
        targetPath = location
        curDir = self.dirTree['root']
        for dir in targetPath:
            if dir in curDir['subdir']:
                if not curDir['subdir'][dir]['isDir']:
                    raise NotADirectoryError('name: "' + dir + '" is not a directory')
                curDir = curDir['subdir'][dir]
            else:
                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['subdir']:
                    if not curDir['subdir'][dir]['isDir']:
                        raise NotADirectoryError('name: "' + dir + '" is not a directory')
                    curDir = curDir['subdir'][dir]
                else:
                    # create new folder
                    newFolder = self.drive.CreateFile(
                        {'title':dir,
                        'parents':[{'id': curDir['id']}],
                        "mimeType": "application/vnd.google-apps.folder"
                        })
                    newFolder.Upload()
                    curDir['subdir'][dir] = {'isDir': True, 'id': newFolder['id'], 'subdir': {}}
                    curDir = curDir['subdir'][dir]
        
        
        gFile = self.drive.CreateFile(
            {'title':filename,
            'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
        })

        gFile.content = data
        gFile.Upload()
        self.__reduceCache()
        if gFile['id'] in self.dataCache:
            self.cacheSize -= self.dataCache[gFile['id']].getbuffer.nbytes
            self.dataCache[gFile['id']].close()
        self.dataCache[gFile['id']] = data
        self.cacheSize += data.getbuffer().nbytes
        curDir['subdir'][filename] = {'id': gFile['id'], 'isDir':False, 'subdir':{}}
        return data

    def download(self, location, filenames):
        targetPath = location
        curDir = self.dirTree['root']
        for dir in targetPath:
            if dir in curDir['subdir']:
                if not curDir['subdir'][dir]['isDir']:
                    raise NotADirectoryError('name: "' + dir + '" is not a directory')
                curDir = curDir['subdir'][dir]
            else:

                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['subdir']:
                    if not curDir['subdir'][dir]['isDir']:
                        raise NotADirectoryError('name: "' + dir + '" is not a directory')
                    curDir = curDir['subdir'][dir]
                else:
                    raise DirectoryNotFoundError('The specified directory: "' +  dir + '" was not found')

        # if cached, not need to connect to Google
        if filenames: 
            for key in list(curDir['subdir'].keys()):
                matchObj = curDir['subdir'][key]
                if all(filename in key for filename in filenames) and not matchObj['isDir'] and matchObj['id'] in self.dataCache:
                    self.dataCache.move_to_end(matchObj['id'])
                    print('cached, no list load')
                    return (key, self.dataCache[matchObj['id']])
        queryStr = ''
        for filename in filenames:
            queryStr += "title contains '" + filename + "' and "
        print("'" + curDir['id'] + "' in parents and " + queryStr + "trashed=false")
        gFiles = self.drive.ListFile({'q': "'" + curDir['id'] + "' in parents and " + queryStr + "trashed=false"}).GetList()

        if not gFiles:
            raise FileNotFoundError('Could not find a file that matches all queries')
        # choose a random file among the ones that matched the query
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

            curDir['subdir'][gFile['title']] = {'id': gFile['id'], 'isDir':False, 'subdir':{}}
            print('not cached')
            return (gFile['title'], gFile.content)
            



    
    def __refreshDir(self, id, curDir):
        ## make a dictionary of subdirectories, with key being the title, and values being dict of id, isDir, and empty subDir
        ## then set it equal to current folder's subdirectory
        curDir['subdir'] = { result['title']:{'id':result['id'], 
        'isDir':(True if result['mimeType'] == 'application/vnd.google-apps.folder' else False), 
        'subdir': {} if result['title'] not in curDir['subdir'] else curDir['subdir'][result['title']]['subdir']} 
        for result in self.drive.ListFile({'q': "'" + id + "' in parents and trashed=false"}).GetList() }

    def __reduceCache(self):
        if self.cacheSize > 262144000:
            for _ in range(50):
                bio = self.dataCache.pop(last = False)
                self.cacheSize -= bio.getbuffer.nbytes
                bio.close()
        else:
            return
