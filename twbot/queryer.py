import os
import asyncio
import audioop
import traceback
import aiohttp
import re

from enum import Enum
from array import array
from collections import deque
from shutil import get_terminal_size
from lxml import etree

import valve.source.a2s as a2s
import valve.source.messages as messages

from .lib.event_emitter import EventEmitter


class ServerQueryer(EventEmitter):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.loop = bot.loop
        self.red = self.blue = self.green = None
        self._query_lock = asyncio.Lock()

    def kill(self):
        self._events.clear()
    
    async def get_tw_players(self):
        with aiohttp.Timeout(10):
            async with self.bot.aiosession.get('http://tribewarfare.apocalypse.gg/api.php?a=getOnlineForTribe&colorindex=1&list=1') as resr:
                # Build tree of players page
                raw = await resr.text()
                tree = etree.HTML(raw)

                # Grab the player info
                redStatus = [e.text for e in tree.xpath('//span')]
                redPlayers = re.findall('(?<=] )[^<]+(?=  <)', raw)
                redList = list(zip(redPlayers, redStatus))

                async with self.bot.aiosession.get('http://tribewarfare.apocalypse.gg/api.php?a=getOnlineForTribe&colorindex=2&list=1') as resg:
                    raw = await resg.text()
                    tree = etree.HTML(raw)
                    greenStatus = [e.text for e in tree.xpath('//span')]
                    greenPlayers = re.findall('(?<=] )[^<]+(?=  <)', raw)
                    greenList = list(zip(greenPlayers, greenStatus))

                    async with self.bot.aiosession.get('http://tribewarfare.apocalypse.gg/api.php?a=getOnlineForTribe&colorindex=3&list=1') as resb:
                        raw = await resb.text()
                        tree = etree.HTML(raw)
                        blueStatus = [e.text for e in tree.xpath('//span')]
                        bluePlayers = re.findall('(?<=] )[^<]+(?=  <)', raw)
                        blueList = list(zip(bluePlayers, blueStatus))
                        return redList, greenList, blueList

    def query(self, message, _continue=False):
        self.loop.create_task(self._query(message, _continue=_continue))

    async def _query(self, message, _continue=False):
        """
            Plays the next entry from the playerlist, or resumes playback of the current entry if paused.
        """
        with await self._query_lock:
            # Query the tribewarfare.apocalypse.gg for id64s of players and respective tribes
            try:
                self.red, self.green, self.blue = await self.get_tw_players()
                self.emit('query-finished', message, self)

            except Exception as e:
                print("Failed to get entry.")
                traceback.print_exc()
                # Retry playing the next entry in a sec.
                self.loop.call_later(0.1, self.query)
                return
