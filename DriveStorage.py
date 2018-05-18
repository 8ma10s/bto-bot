import configparser
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

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


    # upload the file to the specific location
    def upload(self, data, *location):
        targetPath = list(location)
        curDir = self.dirTree['root']
        for dir in targetPath[0:-1]:
            if not curDir['isDir']:
                return None
            elif dir in curDir['subdir']:
                curDir = curDir['subdir'][dir]
            else:
                self.__refreshDir(curDir['id'], curDir)
                if dir in curDir['subdir']:
                    curDir = curDir['subdir'][dir]
                else:
                    return None
        
        ## curDir should now be set to directory in question
        if not curDir['isDir']:
            return None
        
        gFile = self.drive.CreateFile(
            {'title':targetPath[-1],
            'parents':[{'kind': 'drive#fileLink', 'id': curDir['id']}]
        })

        gFile.content = data
        gFile.Upload()
        return data



        
    
    def __refreshDir(self, id, curDir):
        ## make a dictionary of subdirectories, with key being the title, and values being dict of id, isDir, and empty subDir
        ## then set it equal to current folder's subdirectory
        curDir['subdir'] = { result['title']:{'id':result['id'], 
        'isDir':(True if result['mimeType'] == 'application/vnd.google-apps.folder' else False), 'subdir': {}} 
        for result in self.drive.ListFile({'q': "'" + id + "' in parents and trashed=false"}).GetList() }
        

    


