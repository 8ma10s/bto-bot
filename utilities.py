import asyncio
import random
import os


class Utilities:
    """A class that contains all utility functions that are used in the main portion of the program"""
    def __init__(self, client, dataContainer):
        self.client = client
        self.dc = dataContainer
        self.configs = dataContainer.configs
        self.ds = dataContainer.drive

    def isACommand(self, message):
        """Determine whether a message is a command or not.
        Returns a tuple(command_name, args) to be parsed by parseCommand(),
        or None if the message is not a command."""
        
        msg = message.content.lstrip().lstrip(';').split()
        inputCommand = msg[0].lower()
        userCommand = None
        userArgs = None
        # check to see if it's in a list of commands
        for configName, config in self.configs.items():
            for command in config['COMMANDS']:
                if inputCommand == command:
                    userCommand = configName
                    userArgs = msg[1:]
                    break
        
        #check to see if it's one of stamp folders
        if not userCommand:
            if inputCommand.endswith('+'):
                userCommand = 'addStamp'
                userArgs = msg
            elif inputCommand in self.ds.listFiles(self.configs['stamp']['DIR']):
                userCommand = 'stamp'
                userArgs = msg
            else:
                return None
        
        print('Detected command: ' + userCommand)
        return (userCommand, userArgs)

    async def formatArgs(self, message, command, args):
        """This formats the args and returns a list with all necessary parameters for each command.
        If you want to add a new command, this function must be modified."""

        if command in ['stamp', 'addStamp', 'listStamps']:
            # check that invalid characters don't exist
            if any((arg.startswith('.') or \
            any(char in arg for char in ['/', '\\']))\
            for arg in args):
                await self.client.send_message(message.channel, 'ファイル名にクソみたいな文字列を入れるな')
                return None
            else:
                # do final check and format command
                directory = [args[0].rstrip('+').lower()] if len(args) > 0 else []
                if command == 'addStamp':
                    if len(args) < 2 or len(args) > 3:
                        await self.client.send_message(message.channel, '引数の数が多すぎるか少なすぎる')
                    elif not os.path.splitext(args[1])[1]:
                        await self.client.send_message(message.channel, 'ファイル名に拡張子が無い')
                        return None
                    else:
                        return [directory, args[1], (args[2] if len(args) == 3 else None)]
                else:
                    return [directory, args[1:]]
        
        elif command == 'gacha':
            if len(args) > 2:
                await self.client.send_message(message.channel, '引数の数が多すぎる')
                return None
            elif len(args) == 2:
                result = self.validateGacha(args[0], args[1])
                if result['errorMsg'] != None:
                    await self.client.send_message(message.channel, result['errorMsg'])
                    return None
                else:
                    return [result['ren'], result['char'], result['getUr'], result['isGacha']]
            elif len(args) == 1:
                result = self.validateGacha(args[0], None)
                if result['errorMsg'] == None:
                    return [result['ren'], result['char'], result['getUr'], result['isGacha']]
                else:
                    result = self.validateGacha(None, args[0])
                    if result['errorMsg'] == None:
                        return [result['ren'], result['char'], result['getUr'], result['isGacha']]
                    else:
                        await self.client.send_message(message.channel, 'この引数は数字でもキャラでもないよ')
                        return None
            else:
                return []
        
        elif command in ['kill', 'sleep', 'wake', 'dining']:
            if len(args) > 0:
                await self.client.send_message(message.channel, 'このコマンドに引数はありません')
                return None
            else:
                return []
        elif command == 'romLock':
            if len(args) > 1:
                await self.client.send_message(message.channel, '引数が多すぎて杉になりそう')
                return None
            else:
                return args
        else:
            print('Somehow reached an invalid command state. The arguments were: \n' + \
            command + ' ' + str(args))
        



    def validateGacha(self, ren, char):
        config = self.configs['gacha']
        result = {'getUr':False, 'isGacha':True, 'errorMsg':None}

        # validate ren
        if not ren:
            result['ren'] = 1
        elif ren.lower() == 'ur':
            result['ren'] = config['MAX_UR']
            result['getUr'] = True
        else:
            try:
                result['ren'] = int(ren)
                if result['ren'] > config['MAX_GACHA']:
                    result['errorMsg'] = 'せいぜい' + str(config['MAX_GACHA']) + '連までにしような'
            except ValueError:
                result['errorMsg'] = '数字以外を入れるな'
        
        # check char (should either be in gacha character names, or one of directories of stamp)
        if not char:
            result['char'] = None
        elif char.lower() in self.configs['gacha']['NAMES']:
            result['char'] = char.lower()
        elif char.lower() in self.ds.listFiles(self.configs['stamp']['DIR']):
            result['isGacha'] = False
            result['char'] = char.lower()
            if result['getUr']:
                result['errorMsg'] = 'URオプションとスタンプガチャ機能は同時使用できません'
        elif not result['errorMsg']:
            result['errorMsg'] = 'そんなキャラは存在しません！！！'
        else:
            result['errorMsg'] = '数字も間違ってるしキャラも存在してない。あーもうめちゃくちゃだよ'
        
        # return appropriate result
        return result
        


        

        
    async def isAuthorized(self, msg, prompt):
        """Sends the password to this program's owner, and asks for the password. Return the result of validation."""
        passInt = random.randint(0,999)
        print(passInt)
        master = await self.client.get_user_info(self.dc.keys['MY_ID'])
        await self.client.send_message(master, str(passInt))
        await self.client.send_message(msg.channel, prompt)
        answer = await self.client.wait_for_message(timeout = 20, author=msg.author, channel=msg.channel)
        return not (answer == None or str(passInt) != answer.content)

    def getProb(self, card):
        return self.configs['gacha']['PROBS'][card.split('_')[1]]


    async def sayPlease(self, message):
        """Make ROM say please. If properly asked, return True. Else False"""
        config = self.configs['gacha']
        await self.client.send_message(message.channel, '人にものを頼む時はなんて言うんだっけ？')
        reply = await self.client.wait_for_message(timeout = 30, author=message.author, channel=message.channel)
        if not reply:
            await self.client.send_message(message.channel, 'ほう、だんまりか')
            return False
        if reply.author.id not in self.dc.keys['ROM_IDS']:
            await self.client.send_message(message.channel, reply.author.name + 'さんでしたか、これは失礼しました。こちらがご指定のルビィちゃんになります。')
            return True
        elif all(x not in reply.content for x in config['PLS_WORDS']):
            await self.client.send_message(message.channel, 'そんな態度じゃルビィちゃんは出せないなぁ・・・')
            return False
        else:
            await self.client.send_message(message. channel, 'そんなに欲しいならくれてやろう')
            return True