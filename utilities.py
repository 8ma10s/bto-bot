import asyncio
import random


class Utilities:

    def __init__(self, client, dataContainer):
        self.client = client
        self.dc = dataContainer
        self.configs = dataContainer.configs
    
    #def isMsgToMe(self, msg):
        #""" Checks if the message was sent to this bot."""
        #return self.client.user.name in msg.content

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
